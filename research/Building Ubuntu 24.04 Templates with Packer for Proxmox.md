---
tags: [packer, proxmox, ubuntu, automation, infrastructure-as-code, cloud-init, template-creation, virtualization, troubleshooting, autoinstall]
---

# Building Ubuntu 24.04 Templates with Packer for Proxmox

## Overview

This document outlines the process of creating automated Ubuntu 24.04 server templates using HashiCorp Packer with the Proxmox builder. The goal was to create a reusable, automated workflow that could later be extended to build AMIs for AWS and images for other platforms.

## Prerequisites

- Packer v1.14.2 or later
- Proxmox VE server with API access
- Network with DHCP capabilities
- Local workstation with terminal access

## Project Structure

```
packer-ubuntu/
├── ubuntu.pkr.hcl       # Main Packer configuration
├── ubuntu.pkrvars.hcl   # Variable values (gitignored)
├── user-data            # Cloud-init autoinstall config
├── meta-data            # Empty cloud-init metadata file
├── Makefile             # Build automation
└── .gitignore           # Excludes secrets and build artifacts
```

## Initial Setup

### 1. Packer Configuration

Created `ubuntu.pkr.hcl` with the following key components:

**Plugin Declaration:**
```hcl
packer {
  required_plugins {
    proxmox = {
      version = ">= 1.2.3"
      source  = "github.com/hashicorp/proxmox"
    }
  }
}
```

**Variables:**
- `proxmox_url` - API endpoint
- `proxmox_username` - Authentication username
- `proxmox_password` - Authentication password (sensitive)
- `proxmox_node` - Target Proxmox node name

### 2. Source Configuration

The Proxmox ISO builder requires several critical configurations:

**Boot ISO Configuration:**
```hcl
boot_iso {
  iso_url          = "https://releases.ubuntu.com/24.04/ubuntu-24.04.3-live-server-amd64.iso"
  iso_checksum     = "sha256:c3514bf0056180d09376462a7a1b4f213c1d6e8ea67fae5c25099c6fd3d8274b"
  iso_storage_pool = "local"
  unmount          = true
}
```

**VM Hardware Specifications:**
```hcl
memory  = 2048
cores   = 2
sockets = 1
os      = "l26"  # Linux 2.6+ kernel
```

**Network Configuration:**
```hcl
network_adapters {
  model       = "virtio"
  bridge      = "vmbr0"
  mac_address = "repeatable"  # Deterministic MAC based on VM ID
  mtu         = 1              # Inherit MTU from bridge
}
```

**Disk Configuration:**
```hcl
disks {
  type         = "scsi"
  disk_size    = "20G"
  storage_pool = "local"
  format       = "raw"
}
```

### 3. Cloud-Init Integration

Critical for post-installation networking:

```hcl
cloud_init              = true
cloud_init_storage_pool = "local"
qemu_agent              = true
scsi_controller         = "virtio-scsi-single"
```

Without `cloud_init = true`, the VM will not have network configuration after installation completes, resulting in SSH timeout failures.

## Boot Command Configuration

The boot command is critical for triggering the autoinstall process. Ubuntu 24.04 uses a GRUB-based boot menu that requires specific key sequences:

```hcl
boot_wait         = "10s"
boot_key_interval = "150ms"

boot_command = [
  "c<wait>",
  "linux /casper/vmlinuz --- ip=::::::dhcp::: autoinstall ds='nocloud-net;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/'<enter><wait5s>",
  "initrd /casper/initrd<enter><wait5s>",
  "boot<enter><wait5s>"
]
```

**Key Components:**
- `c` - Enters GRUB command line mode
- `ip=::::::dhcp:::` - Kernel parameter for DHCP configuration (colon format required)
- `autoinstall` - Triggers Ubuntu's automated installation
- `ds='nocloud-net;s=http://[...]'` - Cloud-init datasource pointing to HTTP server
- `boot_key_interval = "150ms"` - Slows typing for reliability

## Cloud-Init Autoinstall Configuration

Created `user-data` file with Ubuntu autoinstall schema:

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  network:
    version: 2
    ethernets:
      ens18:
        dhcp4: true
  storage:
    layout:
      name: direct
  identity:
    hostname: ubuntu-template
    username: ubuntu
    password: "[HASHED-PASSWORD]"
  ssh:
    install-server: true
    allow-pw: true
  packages:
    - qemu-guest-agent
    - cloud-init
    - openssh-server
  user-data:
    disable_root: true
  package_update: true
  package_upgrade: true
  early-commands:
    - systemctl stop systemd-networkd-wait-online.service
    - systemctl mask systemd-networkd-wait-online.service
    - echo 'DefaultTimeoutStartSec=30s' >> /etc/systemd/system.conf
    - systemctl daemon-reload
  late-commands:
    - echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/ubuntu
    - chmod 440 /target/etc/sudoers.d/ubuntu
    - curtin in-target --target=/target -- systemctl enable qemu-guest-agent
```

**Critical Components:**

1. **early-commands** - Prevents systemd network wait timeouts that can cause installation to hang
2. **package_update/upgrade** - Ensures template has latest security patches
3. **late-commands** - Configures passwordless sudo and enables QEMU guest agent

### Password Hash Generation

Generate password hash using OpenSSL on macOS:
```bash
openssl passwd -6 ubuntu
```

The empty `meta-data` file must exist even if empty - cloud-init requires it.

## SSH Configuration

```hcl
ssh_username = "ubuntu"
ssh_password = "ubuntu"
ssh_timeout  = "20m"
```

The 20-minute timeout is necessary because:
- Ubuntu installation: 5-7 minutes
- Package updates: 2-3 minutes
- System reboot: 1-2 minutes
- SSH service startup: 30 seconds

## Provisioning

Post-installation provisioning waits for cloud-init completion:

```hcl
provisioner "shell" {
  inline = [
    "while [ ! -f /var/lib/cloud/instance/boot-finished ]; do echo 'Waiting for cloud-init...'; sleep 1; done",
    "sudo apt-get update",
    "sudo apt-get upgrade -y"
  ]
}
```

## Build Automation

Created `Makefile` for common operations:

```makefile
.PHONY: validate build clean fmt

validate:
	packer validate -var-file=ubuntu.pkrvars.hcl ubuntu.pkr.hcl

build:
	packer build -var-file=ubuntu.pkrvars.hcl ubuntu.pkr.hcl

clean:
	rm -rf packer_cache output-* downloaded_iso_path

fmt:
	packer fmt .
```

## Security Considerations

### Credential Management

Created `ubuntu.pkrvars.hcl` for sensitive values:

```hcl
proxmox_url      = "https://[PROXMOX-IP]:8006/api2/json"
proxmox_username = "root@pam"
proxmox_password = "[PASSWORD]"
proxmox_node     = "[NODE-NAME]"
```

### .gitignore Configuration

```
# Packer variable files with secrets
*.pkrvars.hcl

# Packer cache
packer_cache/
downloaded_iso_path/

# Packer output artifacts
output-*/
*.box

# Packer crash logs
crash.log

# macOS files
.DS_Store

# Editor files
.vscode/
```

## Troubleshooting Journey

### Issue 1: Boot Commands Not Working

**Symptom:** VM boots to language selection screen instead of autoinstall.

**Root Cause:** Initial boot command sequence didn't work with Ubuntu 24.04's GRUB menu.

**Solution:** Used `c<wait>` to enter GRUB command mode and manually specify kernel parameters.

### Issue 2: SSH Timeout

**Symptom:** Installation completes but Packer times out waiting for SSH.

**Root Cause:** Missing disk configuration - no disk for Ubuntu to install to.

**Solution:** Added `disks` block with SCSI disk configuration.

### Issue 3: Network Not Available After Installation

**Symptom:** VM boots but has no IP address, SSH unreachable.

**Root Cause:** Missing `cloud_init = true` configuration.

**Solution:** Added cloud-init drive configuration:
```hcl
cloud_init              = true
cloud_init_storage_pool = "local"
```

### Issue 4: Installation Hangs During Network Configuration

**Symptom:** Installation stalls at "Waiting for network" step.

**Root Cause:** `systemd-networkd-wait-online.service` timeout.

**Solution:** Added early-commands to disable network wait services:
```yaml
early-commands:
  - systemctl stop systemd-networkd-wait-online.service
  - systemctl mask systemd-networkd-wait-online.service
```

### Issue 5: Network Interface Name Mismatch

**Symptom:** Specified `ens18` but VM actually used `eth0`.

**Root Cause:** Interface naming depends on network adapter model and configuration.

**Solution:** Network interface names are determined by the adapter model. Using VirtIO typically results in `ens18`, but may vary. The autoinstall configuration can specify the expected interface or omit network config to use defaults.

## Build Process Flow

1. **Initialization**
   - Packer downloads Proxmox plugin
   - ISO is downloaded/cached locally
   - ISO is uploaded to Proxmox storage

2. **VM Creation**
   - Packer creates VM with specified hardware
   - Attaches boot ISO and cloud-init ISO
   - Starts HTTP server serving user-data and meta-data

3. **Boot and Installation**
   - VM boots from ISO
   - Boot commands configure kernel parameters
   - Ubuntu installer fetches autoinstall config via HTTP
   - Automated installation proceeds (5-7 minutes)

4. **Post-Installation**
   - System reboots
   - Cloud-init applies final configuration
   - QEMU guest agent starts
   - SSH service becomes available

5. **Provisioning**
   - Packer connects via SSH
   - Waits for cloud-init completion
   - Runs package updates

6. **Template Creation**
   - VM is stopped
   - VM is converted to template
   - Cloud-init drive is attached
   - Build artifacts are reported

## Successful Build Output

```
Build 'proxmox-iso.ubuntu' finished after 9 minutes 49 seconds.
==> Builds finished. The artifacts of successful builds are:
--> proxmox-iso.ubuntu: A template was created: [TEMPLATE-ID]
```

## Next Steps

### Extending to AWS

To build AMIs for AWS, add an `amazon-ebs` source to the same configuration:

```hcl
source "amazon-ebs" "ubuntu" {
  # AWS-specific configuration
  # Can share the same provisioning steps
}

build {
  sources = [
    "source.proxmox-iso.ubuntu",
    "source.amazon-ebs.ubuntu"
  ]
  
  # Shared provisioning steps
}
```

### ISO Version Management

Consider implementing automated ISO version updates using Renovate or Dependabot by:
1. Storing ISO metadata in a parseable format
2. Configuring version detection rules
3. Automating pull requests for new releases

### Template Testing

Create automated tests to verify template functionality:
1. Deploy VM from template
2. Verify SSH connectivity
3. Check installed packages
4. Validate cloud-init configuration
5. Test QEMU guest agent

## Key Learnings

1. **Cloud-init integration is mandatory** - Without the cloud-init drive, VMs have no network configuration post-installation.

2. **Boot commands are fragile** - Different Ubuntu versions may require different boot command sequences. The `ip=::::::dhcp:::` format (with colons) is required for kernel network configuration.

3. **Timeouts must be generous** - Installation plus updates can take 15+ minutes. Default 10-minute SSH timeout is insufficient.

4. **Early-commands prevent hangs** - Disabling systemd network wait services is critical to prevent installation timeouts.

5. **Disk configuration is required** - The VM needs a disk defined, even though it seems obvious in retrospect.

## References

- [Packer Proxmox Builder Documentation](https://developer.hashicorp.com/packer/plugins/builders/proxmox/iso)
- [Ubuntu Autoinstall Documentation](https://ubuntu.com/server/docs/install/autoinstall)
- [Cloud-init Documentation](https://cloudinit.readthedocs.io/)
- [GitHub Issue #241 - Autoinstall Language Selection Bug](https://github.com/hashicorp/packer-plugin-proxmox/issues/241)

## Conclusion

This configuration provides a reliable, automated method for creating Ubuntu 24.04 templates in Proxmox. The template can be extended to support multiple platforms (AWS, Azure, GCP) while maintaining consistent base configuration through shared provisioning steps. The key to success was understanding the interplay between Packer, Proxmox, Ubuntu's autoinstall system, and cloud-init.