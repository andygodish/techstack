---
tags: [cloud-init, user-data, ubuntu, autoinstall, troubleshooting, configuration, debugging, yaml, proxmox, opentofu]
---

# Understanding Cloud-Init and User-Data Configuration

## What is Cloud-Init?

Cloud-init is the industry-standard multi-distribution method for cross-platform cloud instance initialization. It's supported by all major cloud providers and virtualization platforms.

**Key Concepts:**

- **Datasources**: Where cloud-init gets its configuration (NoCloud, AWS, Azure, OpenStack, etc.)
- **User-data**: Configuration provided at instance creation time
- **Vendor-data**: Optional configuration provided by the platform/cloud provider
- **Metadata**: Instance-specific information (instance ID, hostname, network config)

**Cloud-init runs in stages:**

1. **Local** - Runs early, before networking
2. **Network** - After network is available
3. **Config** - Runs cloud_config modules
4. **Final** - Runs scripts and final modules

## User-Data File Structure

User-data files always start with `#cloud-config` and use YAML syntax:

```yaml
#cloud-config
hostname: my-server
users:
  - name: admin
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAA...
packages:
  - nginx
  - docker.io
runcmd:
  - systemctl enable nginx
```

### Common User-Data Directives

**Users and Authentication:**
```yaml
users:
  - name: username
    groups: [adm, sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false  # Allow password login
    passwd: $6$...      # Hashed password
    ssh_authorized_keys:
      - ssh-rsa AAAA...
```

**System Configuration:**
```yaml
hostname: server-name
fqdn: server-name.domain.local
manage_etc_hosts: true
preserve_hostname: false  # Allow hostname changes
timezone: America/New_York
locale: en_US.UTF-8
```

**Package Management:**
```yaml
package_update: true
package_upgrade: true
packages:
  - package1
  - package2
```

**Network Configuration:**
```yaml
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
```

**Scripts and Commands:**
```yaml
runcmd:
  - echo "Command runs at final stage"
  - systemctl restart service

bootcmd:
  - echo "Command runs at boot stage"
```

## Ubuntu Autoinstall and User-Data

Ubuntu's autoinstall system (subiquity) creates cloud-init configuration during installation. The `user-data` section within autoinstall becomes the cloud-init user-data:

```yaml
#cloud-config
autoinstall:
  version: 1
  identity:
    hostname: ubuntu-template
    username: ubuntu
    password: "$6$..."
  
  # This becomes cloud-init config after installation
  user-data:
    preserve_hostname: false
    users:
      - name: admin
        groups: [sudo]
        ssh_authorized_keys:
          - ssh-rsa AAAA...
```

**Important**: Subiquity automatically adds `preserve_hostname: true` if not specified, which prevents hostname changes via cloud-init after deployment.

## Troubleshooting Cloud-Init

### Essential Log Files

Cloud-init provides detailed logging for debugging configuration issues.

**Primary log file:**
```bash
sudo cat /var/log/cloud-init.log
```
- Complete debug output
- Shows each stage execution
- Module processing details
- Error messages and warnings

**Output log:**
```bash
sudo cat /var/log/cloud-init-output.log
```
- Stdout/stderr from commands
- Package installation output
- Script execution results

**User-data applied to instance:**
```bash
sudo cat /var/lib/cloud/instance/user-data.txt
```
- Shows actual user-data received
- Merged from all sources
- What cloud-init processed

**Cloud-init status:**
```bash
cloud-init status --long
```
- Current status (running, done, disabled, error)
- Boot status code
- Error details if failed

### Common Troubleshooting Commands

**Check if cloud-init has finished:**
```bash
cloud-init status --wait
```
Waits until cloud-init completes before returning.

**View network configuration applied:**
```bash
cat /var/lib/cloud/instance/network-config.json
```

**See combined cloud-config:**
```bash
cat /run/cloud-init/combined-cloud-config.json
```

**Check datasource detected:**
```bash
cat /run/cloud-init/cloud-id
```

**Re-run cloud-init (destructive):**
```bash
sudo cloud-init clean --machine-id
sudo reboot
```

### Reading Cloud-Init Logs

Cloud-init logs use timestamps and severity levels. Key patterns to look for:

**Successful module execution:**
```
handlers.py[DEBUG]: finish: init-network/config-users_groups: SUCCESS: config-users_groups ran successfully
```

**Configuration being skipped:**
```
cc_set_hostname.py[DEBUG]: Configuration option 'preserve_hostname' is set, not setting the hostname
```

**Errors or warnings:**
```
util.py[WARNING]: Failed to set hostname to desired-name
```

**Performance metrics:**
```
performance.py[DEBUG]: Running ['useradd', ...] took 0.040 seconds
```

### Debugging Example: Hostname Not Changing

**Problem**: Deployed VM retains template hostname instead of using cloud-init specified hostname.

**Investigation steps:**

1. Check cloud-init logs:
```bash
sudo grep -i hostname /var/log/cloud-init.log
```

2. Look for `preserve_hostname`:
```bash
sudo grep -i preserve_hostname /var/log/cloud-init.log
```

Output shows:
```
cc_set_hostname.py[DEBUG]: Configuration option 'preserve_hostname' is set, not setting the hostname
```

3. Check user-data configuration:
```bash
sudo cat /var/lib/cloud/instance/user-data.txt | grep -i preserve
```

Shows `preserve_hostname: true` is set.

4. Find the source:
```bash
sudo grep -r "preserve_hostname" /etc/cloud/
```

Found in `/etc/cloud/cloud.cfg.d/99-installer.cfg` (baked into template).

**Solution**: Set `preserve_hostname: false` in template's user-data or in deployment-time cloud-init configuration.

## Configuration Precedence and Merging

Cloud-init loads configuration from multiple sources with specific precedence:

**Precedence (highest to lowest):**
1. Runtime config: `/run/cloud-init/cloud.cfg`
2. Drop-in configs: `/etc/cloud/cloud.cfg.d/*.cfg` (alphabetically, higher numbers override lower)
3. User-data (provided at instance creation)
4. Vendor-data
5. Base config: `/etc/cloud/cloud.cfg`

**Merge strategies:**

- **Dict**: Later values override earlier (default for most keys)
- **List**: Items are appended
- **String**: Later value replaces earlier

**Example of problematic merge:**

Template has `/etc/cloud/cloud.cfg.d/99-installer.cfg`:
```yaml
preserve_hostname: true
```

User-data provides:
```yaml
hostname: new-name
```

Result: hostname directive is ignored because `preserve_hostname: true` wins (loaded after user-data in merge order).

**Fix**: User-data must explicitly override:
```yaml
hostname: new-name
preserve_hostname: false
```

## Cloud-Init with Packer

When building templates with Packer, the autoinstall user-data becomes permanent configuration in the template.

**Template user-data should:**
- Create a bootstrap user with SSH key
- Install base packages
- Apply security hardening
- Set `preserve_hostname: false` to allow customization
- Avoid user-specific configuration

**Deployment-time user-data should:**
- Set hostname
- Add environment-specific users
- Configure application-specific settings
- Override template defaults as needed

## Cloud-Init with OpenTofu/Terraform

Provide user-data at VM deployment using cloud-init snippets:

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
    preserve_hostname: false
    manage_etc_hosts: true
    EOF
    
    file_name = "cloud-init-${var.vm_hostname}.yaml"
  }
}

resource "proxmox_virtual_environment_vm" "server" {
  # ... other config ...
  
  initialization {
    datastore_id      = "local"
    user_data_file_id = proxmox_virtual_environment_file.cloud_init.id
  }
}
```

This allows each VM to have unique configuration while using the same template.

## SSH Key Management

**FIPS compliance considerations:**

Some environments enforce FIPS 140-2 cryptographic standards, which restrict allowed algorithms:

- **Allowed**: ECDSA-256, RSA (with restrictions)
- **Blocked**: Ed25519, ECDSA-521

Check local SSH restrictions:
```bash
cat /etc/ssh/ssh_config.d/fips_ssh_config
```

Generate FIPS-compliant keys:
```bash
ssh-keygen -t ecdsa -b 256
```

Add to user-data:
```yaml
users:
  - name: admin
    ssh_authorized_keys:
      - ecdsa-sha2-nistp256 AAAAE2VjZH...
```

## Best Practices

1. **Separation of concerns**: Template provides base, deployment-time config provides specifics
2. **Always check logs**: Don't assume cloud-init ran successfully
3. **Use `preserve_hostname: false`** in templates unless you have specific reasons not to
4. **Test user-data locally** before deploying to production
5. **Version control user-data**: Treat as infrastructure code
6. **Monitor cloud-init completion**: Use `cloud-init status --wait` in automation
7. **Document expected behavior**: Note what should happen at each cloud-init stage

## Common Pitfalls

**Hostname not changing:**
- Template has `preserve_hostname: true`
- Solution: Override in deployment user-data

**SSH keys not working:**
- Wrong algorithm for security policy
- Permissions on `.ssh` directory incorrect
- User doesn't exist yet

**Network timeout during boot:**
- `systemd-networkd-wait-online.service` blocking
- Solution: Mask the service in early-commands

**Configuration not applying:**
- YAML syntax errors (indentation)
- Wrong datasource detected
- Cloud-init disabled (`/etc/cloud/cloud-init.disabled`)

## Debugging Workflow

When cloud-init doesn't work as expected:

1. **Check if cloud-init ran:**
   ```bash
   cloud-init status --long
   ```

2. **Review logs for errors:**
   ```bash
   sudo grep -i error /var/log/cloud-init.log
   ```

3. **Verify user-data received:**
   ```bash
   sudo cat /var/lib/cloud/instance/user-data.txt
   ```

4. **Check specific module execution:**
   ```bash
   sudo grep "config-MODULE_NAME" /var/log/cloud-init.log
   ```

5. **Review configuration merge:**
   ```bash
   cat /run/cloud-init/combined-cloud-config.json
   ```

6. **Test locally if possible:**
   - Boot with modified user-data
   - Check logs immediately

## References

- [Cloud-init Documentation](https://cloudinit.readthedocs.io/)
- [Ubuntu Autoinstall Reference](https://ubuntu.com/server/docs/install/autoinstall-reference)
- [Cloud-init Examples](https://cloudinit.readthedocs.io/en/latest/reference/examples.html)
- [Network Config v2](https://cloudinit.readthedocs.io/en/latest/reference/network-config-format-v2.html)

## Conclusion

Cloud-init is powerful but requires understanding of:
- Configuration precedence and merging
- Multi-stage execution model
- Datasource detection
- Log analysis for troubleshooting

The key to success is treating it as infrastructure code: version controlled, tested, and well-documented. When issues arise, comprehensive logging makes cloud-init highly debuggable with the right knowledge of where to look.