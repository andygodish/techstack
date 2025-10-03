---
tags: [terraform, opentofu, eks, aws, s3, troubleshooting, state-lock, scp, infrastructure, kubernetes]
---

# Terraform/OpenTofu EKS Module Destruction Issue Summary

## Issue Overview
Attempted to destroy a specific Terraform module (`module.uds_eks`) but encountered multiple blocking issues that prevented successful completion.

## Initial Problem: State Lock
**Error**: State lock acquisition failure
```
Error: Error acquiring the state lock
Lock Info:
  ID:        acc12f21-6f23-4ee3-8d15-436ba37458bb
  Path:      [S3-BUCKET-NAME]/environments/test/terraform.tfstate
  Operation: OperationTypeApply
  Who:       [USERNAME]@[HOSTNAME]
  Created:   2025-09-19 18:53:15.213934 +0000 UTC
```

### Root Cause Analysis
- **Stale lock**: Lock was created on September 19th (9+ days old)
- **VS Code processes**: Multiple `terraform-ls` (Terraform Language Server) processes running since Sept 19th
- **Interrupted operation**: Previous `tofu apply` likely didn't complete cleanly

### Resolution Steps Attempted
1. **Process investigation**: Found old `terraform-ls` processes from Sept 19th
2. **Process termination**: Killed stale language server processes
3. **Force unlock**: Used `tofu force-unlock [LOCK-ID]` to break the stale lock

**Result**: State lock successfully resolved

## Secondary Problem: AWS Service Control Policy (SCP) Restrictions
**Error**: Multiple S3 bucket configuration deletion failures
```
Error: deleting S3 Bucket Lifecycle Configuration ([S3-BUCKET-NAME])
api error AccessDenied: User: [IAM-ROLE-ARN] is not authorized to perform: 
s3:PutLifecycleConfiguration with an explicit deny in a service control policy
```

### Affected Resources
**S3 Bucket Lifecycle Configurations**:
- `module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-admin"].aws_s3_bucket_lifecycle_configuration.this[0]`
- `module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-chunks"].aws_s3_bucket_lifecycle_configuration.this[0]`
- `module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-ruler"].aws_s3_bucket_lifecycle_configuration.this[0]`
- `module.uds_core.module.velero_s3_bucket.module.s3_bucket["velero"].aws_s3_bucket_lifecycle_configuration.this[0]`

**S3 Bucket Encryption Configurations**:
- `module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-admin"].aws_s3_bucket_server_side_encryption_configuration.this[0]`
- `module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-chunks"].aws_s3_bucket_server_side_encryption_configuration.this[0]`
- `module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-ruler"].aws_s3_bucket_server_side_encryption_configuration.this[0]`
- `module.uds_core.module.velero_s3_bucket.module.s3_bucket["velero"].aws_s3_bucket_server_side_encryption_configuration.this[0]`
- `module.uds_core.module.zarf_s3_bucket.module.s3_bucket["zarf"].aws_s3_bucket_server_side_encryption_configuration.this[0]`

### Root Cause
- **Organization-level SCP**: Explicit deny policy preventing S3 configuration modifications
- **Blocked permissions**: `s3:PutLifecycleConfiguration` and `s3:PutEncryptionConfiguration`
- **API behavior**: S3 uses "Put" operations for all configuration changes, including deletions

### Bucket Purpose Analysis
- **Loki buckets**: Log aggregation system storage (admin, chunks, ruler)
- **Velero bucket**: Kubernetes backup storage
- **Zarf bucket**: Software packaging/deployment tool storage

## Proposed Solutions

### Option 1: State Manipulation (Recommended)
Remove problematic resources from Terraform state without destroying them:
```bash
tofu state rm 'module.uds_core.module.loki_s3_bucket.module.s3_bucket["loki-admin"].aws_s3_bucket_lifecycle_configuration.this[0]'
# ... repeat for all problematic resources
```

**Pros**: Allows destroy to proceed immediately
**Cons**: Resources become orphaned, potential naming conflicts on future applies

### Option 2: Manual AWS CLI Cleanup
Attempt manual deletion before state removal:
```bash
aws s3api delete-bucket-lifecycle --bucket [S3-BUCKET-NAME]
aws s3api delete-bucket-encryption --bucket [S3-BUCKET-NAME]
```

**Pros**: Cleaner approach if successful
**Cons**: Likely to fail due to same SCP restrictions

### Option 3: Targeted Destruction with Exclusions
Use exclude flags to skip problematic resources:
```bash
tofu destroy -target=module.uds_eks -exclude='[PROBLEMATIC-RESOURCE-1]' -exclude='[PROBLEMATIC-RESOURCE-2]'
```

**Pros**: Keeps resources in state for future management
**Cons**: Command becomes very long with many exclusions

### Option 4: Administrative Intervention
Request temporary SCP modification or admin-level cleanup

**Pros**: Complete resolution without orphaned resources
**Cons**: Requires organizational approval and coordination

## Key Findings

### Terraform Language Server Impact
- VS Code's Terraform extension runs persistent background processes
- These processes can interfere with state management
- Old processes may hold references to stale operations
- **Recommendation**: Regularly restart VS Code when working with Terraform

### Service Control Policy Implications
- Organization-level policies can block infrastructure destruction
- S3 configuration resources are particularly restricted in government environments
- Standard admin roles may not have sufficient permissions
- **Recommendation**: Review SCP policies before large infrastructure changes

### Module Dependencies
- `module.uds_eks` destruction was blocked by `module.uds_core` resources
- Cross-module dependencies can create unexpected destroy failures
- **Recommendation**: Map resource dependencies before targeted operations

## Next Steps
1. **Immediate**: Decide on solution approach (state removal vs. admin intervention)
2. **Short-term**: Complete EKS module destruction
3. **Long-term**: Address orphaned resources to prevent future naming conflicts
4. **Process improvement**: Document SCP restrictions for team awareness

## Prevention Strategies
- **Regular cleanup**: Periodically restart development tools to prevent stale processes
- **State lock monitoring**: Implement alerts for long-running state locks
- **Permission auditing**: Document SCP restrictions affecting infrastructure operations
- **Dependency mapping**: Create visual maps of inter-module dependencies before major changes