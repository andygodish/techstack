---
tags: [zarf, gitea, backup, restore, k3d, sqlite, kubernetes, data-migration, filesystem, troubleshooting]
---

# Zarf Gitea Backup and Restore Procedure

## Overview

This document outlines the process for backing up and restoring Gitea data between Zarf-deployed instances running on k3d clusters. The procedure uses filesystem-level backup through direct k3d container access for optimal performance and data integrity.

This example was completed using the default values in the Zarf init package. A single PVC mounted to the Gitea pod with SQLite as the database backend.

## Architecture Context

### Zarf Gitea Storage Configuration
- **Database Backend**: SQLite3 (single-file database)
- **Storage Type**: Kubernetes PVC with ReadWriteOnce access mode
- **Storage Class**: `local-path` (k3d default)
- **Data Mount Point**: `/data` inside Gitea pod
- **Persistence**: 10Gi PVC (configurable via `GIT_SERVER_PVC_SIZE`)

### Storage Limitations
- **Single Replica Constraint**: SQLite prevents multiple concurrent writers
- **No Volume Snapshots**: Local-path storage class doesn't support snapshots
- **Node Affinity**: ReadWriteOnce requires pods on same node for multi-pod scenarios

## Data Structure

### Gitea Data Layout (`/data`)
```
/data/
├── git/
│   └── gitea-repositories/
│       └── [USERNAME]/
│           └── [REPO-NAME].git/  # Bare Git repositories
├── gitea/
│   ├── conf/           # Gitea configuration
│   ├── gitea.db        # SQLite database
│   └── log/            # Application logs
├── actions_artifacts/   # CI/CD artifacts
├── attachments/        # File uploads
├── avatars/            # User avatars
└── tmp/                # Temporary files
```

### Repository Storage Format
Gitea stores repositories as **bare Git repositories** containing:
- Git object database (`objects/`)
- References (`refs/`)
- Configuration (`config`)
- Logs and hooks

The Gitea UI dynamically reconstructs working directory views from bare repository data without maintaining checked-out files.

## Backup Procedure

### Prerequisites
- Access to source k3d cluster
- SSH access to remote target system
- kubectl configured for source cluster

### Step 1: Identify Storage Components
```bash
# Get Gitea pod information
kubectl get pods -n zarf -l app.kubernetes.io/name=gitea -o wide

# Identify PVC and PV
kubectl get pvc -n zarf
kubectl get pv [PV-NAME] -o yaml | grep hostPath -A 2
```

### Step 2: Scale Down Application
```bash
# Stop Gitea to ensure SQLite consistency
kubectl scale -n zarf deployment/zarf-gitea --replicas=0
kubectl wait --for=delete pod -l app.kubernetes.io/name=gitea -n zarf --timeout=60s
```

### Step 3: Create Filesystem Backup
```bash
# Identify k3d container
docker ps | grep k3d-[CLUSTER-NAME]-server

# Create backup from k3d container storage
docker exec -it [K3D-CONTAINER] tar czf /tmp/gitea-backup.tar.gz \
  -C /opt/local-path-provisioner-rwx/[PVC-PATH] .

# Copy backup from container
docker cp [K3D-CONTAINER]:/tmp/gitea-backup.tar.gz \
  ./gitea-backup-$(date +%Y%m%d-%H%M%S).tar.gz
```

### Step 4: Restart Application
```bash
kubectl scale -n zarf deployment/zarf-gitea --replicas=1
```

### Step 5: Transfer Backup
```bash
scp ./gitea-backup-*.tar.gz [REMOTE-HOST]:/tmp/
```

## Restore Procedure

### Prerequisites
- Backup file transferred to target system
- Target Zarf cluster with Gitea component deployed
- Matching Zarf configuration between source and target

### Step 1: Scale Down Target Application
```bash
# On target system
kubectl scale -n zarf deployment/zarf-gitea --replicas=0
kubectl wait --for=delete pod -l app.kubernetes.io/name=gitea -n zarf --timeout=60s
```

### Step 2: Identify Target Storage
```bash
# Get target PVC path
kubectl get pv -o yaml | grep hostPath -A 1
```

### Step 3: Clear Existing Data
```bash
# Access target k3d container
docker exec -it [TARGET-K3D-CONTAINER] /bin/sh

# Navigate to target data directory
cd /opt/local-path-provisioner-rwx/[TARGET-PVC-PATH]

# Remove existing data
rm -rf ./*
```

### Step 4: Restore Backup
```bash
# Copy backup into target container
docker cp /tmp/gitea-backup-*.tar.gz [TARGET-K3D-CONTAINER]:/tmp/

# Extract backup in target container
tar xzf /tmp/gitea-backup-*.tar.gz
```

### Step 5: Restart Target Application
```bash
kubectl scale -n zarf deployment/zarf-gitea --replicas=1
```

## Verification Steps

### Post-Restore Validation
1. **Service Accessibility**: Verify Gitea UI loads via port-forward
2. **Authentication**: Test login with migrated user accounts
3. **Repository Access**: Confirm repositories display correctly
4. **Git Operations**: Test clone/push operations
5. **Database Integrity**: Check for SQLite corruption

### Troubleshooting Access

For remote cluster access via SSH tunnel:
```bash
# Create SSH tunnel (local machine)
ssh -L [LOCAL-PORT]:127.0.0.1:[REMOTE-PORT] -N [REMOTE-HOST]

# Port-forward on remote machine
kubectl port-forward -n zarf service/zarf-gitea-http [PORT]:3000
```

## Production Considerations

### High Availability Limitations
Current Zarf Gitea configuration has inherent HA limitations:
- **SQLite Database**: Single-process, no concurrent writes
- **ReadWriteOnce Storage**: Single-pod constraint
- **Recreate Strategy**: Downtime during updates

### Recommendations for Production
1. **Database Backend**: Migrate to PostgreSQL for HA support
2. **Storage Strategy**: Implement volume snapshots where available
3. **Automation**: Integrate with Velero for scheduled backups
4. **Monitoring**: Add backup success/failure alerting

### Velero Integration
For automated backups, Velero requires application-aware hooks:
```yaml
hooks:
  resources:
    pre:
    - exec:
        command: ["/bin/sh", "-c", "kubectl scale deployment zarf-gitea --replicas=0 -n zarf"]
    post:
    - exec:
        command: ["/bin/sh", "-c", "kubectl scale deployment zarf-gitea --replicas=1 -n zarf"]
```

## Alternative Backup Methods

### Volume Snapshot (if supported)
```bash
kubectl create volumesnapshot gitea-snapshot \
  --from-pvc=data-zarf-gitea-0 -n zarf
```

### Pod-Based Backup (slower alternative)
```bash
kubectl exec -n zarf [GITEA-POD] -- tar czf /tmp/backup.tar.gz -C /data .
kubectl cp zarf/[GITEA-POD]:/tmp/backup.tar.gz ./backup.tar.gz
```

## Security Notes

- Backup files contain sensitive data including user credentials
- SQLite database includes hashed passwords and authentication tokens
- Git repositories may contain sensitive source code or configurations
- Ensure backup files are encrypted in transit and at rest
- Implement proper access controls for backup storage locations

## Recovery Time Objectives

**Typical Performance Metrics:**
- **Backup Creation**: 2-5 minutes for moderate data volumes
- **Transfer Time**: Dependent on network bandwidth
- **Restore Time**: 1-3 minutes for filesystem extraction
- **Application Startup**: 30-60 seconds for Gitea pod initialization
- **Total RTO**: 5-15 minutes for complete disaster recovery