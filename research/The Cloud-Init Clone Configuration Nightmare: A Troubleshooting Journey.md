---
tags: [cloud-init, proxmox, troubleshooting, opentofu, terraform, packer, ubuntu, autoinstall, debugging, infrastructure-as-code, template-cloning]
---

# The Cloud-Init Clone Configuration Nightmare: A Troubleshooting Journey

## The Goal

Deploy VMs from a Packer-built Ubuntu 24.04 template using OpenTofu, with each VM having a unique hostname set via cloud-init at deployment time.

**Expected workflow:**
1. Packer builds template with generic hostname "ubuntu-template"
2. OpenTofu clones template to create new VM
3. OpenTofu provides cloud-init user-data snippet with custom hostname
4. VM boots with the custom hostname

**Reality:** VM always boots with "ubuntu-template" hostname, completely ignoring the cloud-init configuration.

## The Core Problem

Ubuntu's autoinstall installer **intentionally disables cloud-init** after installation completes. This is by design - autoinstall assumes you're doing a one-time installation, not creating a reusable template.

When the Packer template is built:
1. Autoinstall runs and configures the system
2. Autoinstall creates `/etc/cloud/cloud-init.disabled` as its final action
3. Template is saved with cloud-init permanently disabled

When VMs are cloned from this template:
1. VM inherits `/etc/cloud/cloud-init.disabled`
2. Cloud-init checks for this file at boot
3. Cloud-init exits immediately without processing any configuration
4. OpenTofu's cloud-init snippet is completely ignored

## Initial Troubleshooting

### Attempt 1: Basic Cloud-Init Snippet

Created OpenTofu configuration to provide hostname via cloud-init:

```hcl
resource "proxmox_virtual_environment_file" "cloud_init" {
  content_type = "snippets"
  datastore_id = "local"
  node_name    = var.proxmox_node

  source_raw {
    data = <<-EOF
    #cloud-config
    hostname: ${var.vm_hostname}
    fqdn: ${var.vm_hostname}.local
    manage_etc_hosts: true
    EOF
    
    file_name = "cloud-init-${var.vm_hostname}.yaml"
  }
}
```

**Result:** Hostname unchanged. VM still named "ubuntu-template".

**Investigation:** Checked cloud-init status on deployed VM:
```bash
cloud-init status --long
```

Output:
```
status: disabled
boot_status_code: disabled-by-marker-file
detail: Cloud-init disabled by /etc/cloud/cloud-init.disabled
```

**Discovery:** Cloud-init was disabled and never processed our configuration.

### Attempt 2: Configuration Precedence Override

**Theory:** Maybe the template's cloud-init configuration has `preserve_hostname: true` and we need to override it.

Updated snippet:
```yaml
#cloud-config
hostname: ${var.vm_hostname}
preserve_hostname: false
```

**Result:** No change. Still disabled.

**Lesson:** Can't override configuration that never gets processed in the first place.

### Attempt 3: Investigating Template Configuration

Examined the template's cloud-init configuration:

```bash
# Check Proxmox cloud-init drive
qm cloudinit dump 111 user

# Check filesystem config
cat /etc/cloud/cloud.cfg.d/99-installer.cfg
```

**Findings:**
1. Proxmox cloud-init drive showed basic config (hostname, users)
2. Inside the template's filesystem: `/etc/cloud/cloud.cfg.d/99-installer.cfg` contained `preserve_hostname: true`
3. `/etc/cloud/cloud-init.disabled` existed with content:
   ```
   Disabled by Ubuntu live installer after first boot.
   To re-enable cloud-init on this image run:
     sudo cloud-init clean --machine-id
   ```

**Understanding:** Multiple issues compounding:
- Cloud-init is disabled (primary issue)
- Even if enabled, `preserve_hostname: true` would block hostname changes
- Configuration precedence: files in `/etc/cloud/cloud.cfg.d/99-*` override user-data

## Fixing the Template

### Attempt 4: Disable preserve_hostname in Packer

Updated Packer's autoinstall user-data:

```yaml
user-data:
  preserve_hostname: false
  users:
    - name: andy
      # ... user config
```

Rebuilt template, deployed VM.

**Result:** No change. `preserve_hostname` setting didn't make it into the template.

**Reason:** The `user-data` section in autoinstall doesn't write to `/etc/cloud/cloud.cfg.d/` directly. Autoinstall generates its own config files after processing user-data.

### Attempt 5: Remove cloud-init.disabled in late-commands

Added to Packer's autoinstall late-commands:

```yaml
late-commands:
  - curtin in-target --target=/target -- rm -f /etc/cloud/cloud-init.disabled
```

Rebuilt template, deployed VM.

**Result:** File still exists in deployed VMs.

**Investigation:** Checked file timestamp:
```bash
ls -la /etc/cloud/cloud-init.disabled
-rw-r--r-- 1 root root 132 Oct 4 04:34 /etc/cloud/cloud-init.disabled
```

Timestamp showed file was created AFTER our late-commands ran.

**Discovery:** Autoinstall runs late-commands, then creates `/etc/cloud/cloud-init.disabled` as its absolute final step. We can't delete it because it doesn't exist yet when our commands run.

### Attempt 6: Override write_files Directive

**Theory:** Autoinstall uses a `write_files` directive to create the disabled file. Override it with empty array.

```yaml
user-data:
  write_files: []
  preserve_hostname: false
```

**Result:** Packer validation error:
```
Cloud config schema errors: autoinstall.user-data.write_files: [] is too short
```

**Lesson:** Can't use empty arrays for certain cloud-init directives. Schema validation prevents it.

### Attempt 7: Systemd Service to Re-enable Cloud-Init

Created a systemd oneshot service to remove the disabled file before cloud-init runs:

```yaml
late-commands:
  - |
    cat > /target/etc/systemd/system/enable-cloud-init.service << 'EOF'
    [Unit]
    Description=Re-enable cloud-init for cloned VMs
    Before=cloud-init-local.service
    ConditionPathExists=/etc/cloud/cloud-init.disabled

    [Service]
    Type=oneshot
    ExecStart=/bin/rm -f /etc/cloud/cloud-init.disabled
    RemainAfterExit=yes

    [Install]
    WantedBy=cloud-init.target
    EOF
  - curtin in-target --target=/target -- systemctl enable enable-cloud-init.service
```

**Result:** Service exists but never runs.

**Investigation:**
```bash
systemctl status enable-cloud-init.service
# Output: inactive (dead)

journalctl -u enable-cloud-init.service -b
# Output: -- No entries --
```

**Analysis:** The service is enabled but never executes. Problem with ordering:
1. Cloud-init checks for `/etc/cloud/cloud-init.disabled` very early in boot
2. If found, cloud-init exits immediately
3. `cloud-init.target` is never reached because cloud-init disabled itself
4. Our service never triggers because it's waiting for a target that never activates

**The catch-22:** Need cloud-init to run to trigger our service, but the disabled file prevents cloud-init from running.

## Understanding Configuration Merge Order

Cloud-init loads configuration from multiple sources with specific precedence:

**Load Order (highest to lowest priority):**
1. `/run/cloud-init/cloud.cfg` (runtime config)
2. `/etc/cloud/cloud.cfg.d/*.cfg` (alphabetically, 99-* loads last)
3. User-data from datasource (our OpenTofu snippet)
4. `/etc/cloud/cloud.cfg` (base config)

**The problem:**
- Our OpenTofu snippet provides user-data with `hostname` and `preserve_hostname: false`
- Template has `/etc/cloud/cloud.cfg.d/99-installer.cfg` with `preserve_hostname: true`
- The `99-installer.cfg` loads AFTER user-data in the merge
- Result: `preserve_hostname: true` wins, our hostname directive is ignored

**Even if we fixed the disabled file**, the configuration precedence would still block us.

## The Solution: Bypass Cloud-Init Entirely

After exhausting cloud-init approaches, switched to direct SSH provisioning:

```hcl
resource "proxmox_virtual_environment_vm" "test_vm" {
  # ... VM configuration ...

  connection {
    type        = "ssh"
    user        = "andy"
    private_key = file("~/.ssh/id_ecdsa")
    host        = self.ipv4_addresses[1][0]
  }

  provisioner "remote-exec" {
    inline = [
      "sudo hostnamectl set-hostname ${var.vm_hostname}",
      "sudo sed -i 's/ubuntu-template/${var.vm_hostname}/g' /etc/hosts"
    ]
  }
}
```

**How it works:**
1. VM boots from template (with hostname "ubuntu-template")
2. OpenTofu waits for SSH to become available
3. OpenTofu connects and executes commands directly
4. `hostnamectl` sets the hostname immediately
5. `/etc/hosts` is updated to reflect new hostname

**Result:** Success. Hostname changes reliably on every deployment.

## Why the Remote-Exec Solution Works

**Advantages over cloud-init:**
1. **No disabled file issues** - Bypasses cloud-init entirely
2. **No precedence conflicts** - Direct system commands, no config merging
3. **Immediate feedback** - See command output, errors are obvious
4. **Debugging is straightforward** - SSH in and run commands manually
5. **Works with any template** - Doesn't require cloud-init to be enabled

**Disadvantages:**
1. **Requires network/SSH** - VM must be accessible and have SSH running
2. **Not idempotent by default** - Commands run every time (can be mitigated)
3. **Credentials needed** - Must have SSH key or password
4. **Serial execution** - Provisioners run sequentially, slower for many VMs

## Lessons Learned

### 1. Autoinstall Templates Are Not Cloud-Init Friendly

Ubuntu's autoinstall is designed for **one-time installations**, not reusable templates. The installer's final action is to disable cloud-init because it assumes provisioning is complete.

**Implications:**
- Templates built with autoinstall will have cloud-init disabled by default
- Cloud-init snippets provided at clone time will be ignored
- This is intentional behavior, not a bug

**Workarounds:**
- Use SSH provisioners instead of cloud-init
- Use Ansible for post-deployment configuration
- Build templates differently (not with autoinstall)

### 2. Configuration Precedence Matters

Even if cloud-init were enabled, configuration precedence would create problems:

**The precedence chain:**
```
/etc/cloud/cloud.cfg.d/99-installer.cfg (highest priority)
    ↓
User-data from datasource (our snippet)
    ↓
/etc/cloud/cloud.cfg (base config)
```

Files numbered `99-*` intentionally load last to override everything else. The installer uses this to enforce its settings.

**Takeaway:** When building templates, be aware of what gets baked into `/etc/cloud/cloud.cfg.d/`. Higher-numbered files will override user-data provided at deployment time.

### 3. Late-Commands Have Timing Limitations

Autoinstall's execution order:
1. System installation
2. Package installation  
3. User-data processing
4. **Late-commands execution**
5. **Autoinstall creates `/etc/cloud/cloud-init.disabled`** (FINAL STEP)

You cannot prevent autoinstall from creating the disabled file because it happens after late-commands complete.

**Workarounds attempted:**
- Delete file in late-commands → File doesn't exist yet
- Systemd service to delete on boot → Service never runs because cloud-init disabled
- Override write_files → Schema validation prevents empty array

**No viable solution** within the autoinstall/cloud-init framework.

### 4. Debug Cloud-Init Issues Systematically

**Essential debugging workflow:**

1. **Check if cloud-init ran:**
   ```bash
   cloud-init status --long
   ```

2. **Examine logs for errors:**
   ```bash
   grep -i error /var/log/cloud-init.log
   ```

3. **Verify user-data received:**
   ```bash
   cat /var/lib/cloud/instance/user-data.txt
   ```

4. **Check configuration sources:**
   ```bash
   ls -la /etc/cloud/cloud.cfg.d/
   cat /etc/cloud/cloud.cfg.d/99-*.cfg
   ```

5. **Review merged configuration:**
   ```bash
   cat /run/cloud-init/combined-cloud-config.json
   ```

6. **Check for disabled file:**
   ```bash
   ls -la /etc/cloud/cloud-init.disabled
   ```

This systematic approach quickly identified that cloud-init was disabled, saving hours of debugging configuration issues that were irrelevant.

### 5. Sometimes the "Simple" Solution Is Best

After trying:
- Configuration overrides
- Template rebuilds
- Systemd services
- Custom scripts
- File removal in various boot stages

The solution was: **SSH in and run the command directly.**

**Why this works better:**
- **Visible** - You see exactly what runs
- **Reliable** - No hidden configuration precedence
- **Debuggable** - Errors are immediate and clear
- **Flexible** - Easy to add more commands
- **Portable** - Works on any SSH-accessible system

Sometimes fighting a framework's design is harder than working around it.

## Alternative Approaches

### Option 1: Don't Use Autoinstall for Templates

Build templates using a different method:
- Manual installation + sysprep
- Cloud images as base (already cloud-init ready)
- Packer with different provisioners (ansible, shell)

**Pros:** Cloud-init works as expected
**Cons:** Loses autoinstall's automation benefits

### Option 2: Accept Limitations, Use Ansible

Keep autoinstall templates but use Ansible for customization:

1. Packer builds minimal template (base packages only)
2. OpenTofu deploys VM from template
3. Ansible playbook configures hostname, users, applications

**Pros:** 
- Ansible is purpose-built for configuration management
- Idempotent, testable, reusable
- Works for VMs and bare metal

**Cons:**
- Additional tool/complexity
- Requires Ansible knowledge

### Option 3: One Template Per Configuration

Build specific templates for specific purposes:

- `web-server-template` (hostname: web-server)
- `database-template` (hostname: database)

**Pros:** No runtime configuration needed
**Cons:** Template proliferation, harder to maintain

## When to Use Each Approach

**Use Cloud-Init when:**
- Building from cloud-ready images (not autoinstall)
- First-boot configuration on fresh installs
- Providers require it (AWS, Azure, GCP)
- Template doesn't disable cloud-init

**Use SSH Provisioners when:**
- Working with autoinstall templates
- Need simple, reliable configuration
- Configuration is straightforward (hostname, users, basic setup)
- Immediate feedback is important

**Use Ansible when:**
- Complex, multi-step configurations
- Need idempotency
- Managing both VMs and bare metal
- Configuration needs to be version controlled and tested
- Application deployment and lifecycle management

## Conclusion

The cloud-init clone configuration problem was a collision of design philosophies:

1. **Autoinstall's design:** One-time installation, disable cloud-init when done
2. **Template workflow needs:** Reusable base, customize at deployment
3. **Cloud-init's model:** Configure at first boot

These are fundamentally incompatible. Autoinstall templates will always disable cloud-init, making clone-time cloud-init configuration impossible without workarounds.

**The lesson:** Don't fight a tool's design. When autoinstall disables cloud-init by design, the solution isn't to re-enable it through increasingly complex hacks. The solution is to use a different tool (SSH provisioners, Ansible) that aligns with your workflow.

**Final wisdom:** The "nightmare" wasn't technical complexity - it was assuming cloud-init should work in a scenario it was never designed for. Understanding the design intent would have saved hours of troubleshooting.

Templates built with autoinstall are **immutable golden images**, not cloud-init platforms. Treat them accordingly.