---
tags: [JG, kubernetes, secrets, configmap, helm, license-management, volume-mounting, troubleshooting, deployment, file-systems]
---

# Kubernetes License File Mount Troubleshooting Guide

This serves as a good reference for how licenses are consumed as part of the JG project. 

## Problem Summary

Fixed conflicting volume mounts that prevented Kubernetes pods from starting due to license file mounting errors. The root cause was attempting to mount individual files into directories already occupied by ConfigMap mounts.

## Root Cause Analysis

### The Core Issue
Kubernetes cannot mount individual files directly into paths that are already mount points for other volumes. The error manifested as:

```
error mounting "/var/lib/kubelet/pods/.../volume-subpaths/[SECRET-NAME]/[CONTAINER]/[ID]" to rootfs at "/entrypoint/[LICENSE-FILE]": ... not a directory: unknown
```

### Original Broken Configuration
Both engine and scheduler components had the same fundamental problem:

```yaml
volumeMounts:
- name: entrypoint-configmap
  mountPath: /entrypoint                    # ConfigMap occupies entire directory
- name: license-secret
  mountPath: /entrypoint/[LICENSE-FILE]     # CONFLICT: Can't mount file here
  subPath: [LICENSE-FILE]
```

This created a mount conflict because `/entrypoint` was already occupied by the ConfigMap volume.

## Solution Architecture

### Strategy: Separate Mount Paths
Instead of mounting license files into the ConfigMap directory, we mount them to dedicated paths and copy at runtime.

#### Engine Component Fix

**Volume Mounts:**
```yaml
volumeMounts:
- name: engine-entrypoint
  mountPath: /entrypoint                    # ConfigMap scripts and configs
- name: license-secret
  mountPath: /license-mount                 # License Secret (separate path)
```

**Runtime Logic:**
```bash
# Check source mount
if [ -f "/license-mount/SLicense.dat" ]; then
    mkdir -p /Data/AS/License
    cp /license-mount/SLicense.dat /Data/AS/License/SLicense.dat
else
    exit 1
fi
```

#### Scheduler Component Fix

**Volume Mounts:**
```yaml
volumeMounts:
- name: scheduler-entrypoint
  mountPath: /entrypoint                    # ConfigMap scripts and configs
- name: scheduler-license
  mountPath: /license-mount                 # License Secret (separate path)
```

**Runtime Logic:**
```bash
# Check source mount
if [ -f "/license-mount/AS.license" ]; then
    cp /license-mount/AS.license "$LICENSE_DIR/AS.license"
else
    echo "License file not found"
fi
```

## License File Journey

### Complete Flow for Both Components

1. **Helm Values Storage**
   - License stored as base64 in values files: `[VALUES].engine.license.engineLicense`
   - Values remain encoded for secure storage

2. **Kubernetes Secret Creation**
   - Helm creates Secret with decoded binary license data
   - Secret contains the actual license file content (not base64 text)

3. **Volume Mount Strategy**
   - ConfigMap mounts to `/entrypoint/` with scripts and configurations
   - License Secret mounts to `/license-mount/` with license files
   - No path conflicts between mounts

4. **Runtime File Copy**
   - Entrypoint script copies from mount to application directory
   - Engine: `/license-mount/SLicense.dat` → `/Data/AS/License/SLicense.dat`
   - S: `/license-mount/AS.license` → `/Data/License/AScheduler.license`

5. **Application Usage**
   - Applications read license from final destination paths
   - Paths configured in respective config files point to copied locations

## Base64 Decoding Evolution

### The Legacy Approach Problem
Earlier versions of the configuration were handling license decoding manually in the entrypoint scripts, which caused unnecessary complexity and potential failure points.

**Old Approach (Problematic):**
```bash
# Scheduler script was doing manual base64 decoding
if [ -f "/entrypoint/AScheduler.license" ]; then
    echo "Decoding base64 license content..."
    cat /entrypoint/AScheduler.license | base64 -d > "$LICENSE_DIR/AScheduler.license"
fi
```

**Problems with Manual Decoding:**
- Added unnecessary processing step in container startup
- Created potential failure point if base64 data was malformed
- Inconsistent handling between components
- Made troubleshooting more complex
- Risk of data corruption during decode process

### Current Approach (Simplified)
Kubernetes Secrets automatically handle base64 decoding when the Secret is created from Helm values.

**Secret Creation Process:**
1. **Helm Values**: License stored as base64 string in values file
2. **Secret Template**: Helm template creates Secret with the base64 data
3. **Kubernetes Processing**: Kubernetes automatically decodes base64 data when Secret is created
4. **Mount Result**: Files mounted from Secret are already in binary format

**Current Script Logic (Simple Copy):**
```bash
# Engine - direct binary copy
cp /license-mount/SchedulerLicense.dat /Data/AScheduler/License/SchedulerLicense.dat

# Scheduler - direct binary copy  
cp /license-mount/AScheduler.license "$LICENSE_DIR/AScheduler.license"
```

### Why This Works Better

**Kubernetes Secret Behavior:**
- When you put base64 data in a Secret's `data` field, Kubernetes decodes it automatically
- When the Secret is mounted as a volume, files contain the decoded binary content
- No manual decoding required in application logic

**Benefits:**
- Eliminates processing overhead in container startup
- Reduces failure points in the license handling pipeline
- Consistent behavior across all components
- Simpler troubleshooting (just verify file copy, not decode process)
- More reliable license file integrity

**Secret YAML Structure:**
```yaml
apiVersion: v1
kind: Secret
type: Opaque
data:
  SchedulerLicense.dat: {{ .Values.engine.license.engineLicense }}
  # Kubernetes automatically decodes this base64 string to binary when Secret is created
```

### Migration Impact
This change simplified the license handling significantly:
- **Before**: Values → ConfigMap → Manual decode → Application
- **After**: Values → Secret (auto-decode) → Direct copy → Application

The elimination of manual base64 decoding removed a common source of license-related startup failures and made the overall system more reliable.

## Key Configuration Changes

### Deployment YAML Changes

**Old (Broken):**
```yaml
- name: license-secret
  mountPath: /entrypoint/[LICENSE-FILE]
  subPath: [LICENSE-FILE]
```

**New (Working):**
```yaml
- name: license-secret
  mountPath: /license-mount
# Remove subPath entirely
```

### ConfigMap Script Changes

**Logic Fix:**
- Changed from checking destination file (which doesn't exist yet)
- To checking source mount file (which should exist)
- Added proper error handling and debugging output

**Before:**
```bash
if [ -f "/Data/AScheduler/License/SchedulerLicense.dat" ]; then
    # This check always failed on first run
```

**After:**
```bash
if [ -f "/license-mount/SchedulerLicense.dat" ]; then
    mkdir -p /Data/AScheduler/License
    cp /license-mount/SchedulerLicense.dat /Data/AScheduler/License/SchedulerLicense.dat
```

## Path Mapping Reference

| Component | Source Mount Path | Final Destination | Config Reference |
|-----------|------------------|------------------|------------------|
| Engine | `/license-mount/SchedulerLicense.dat` | `/Data/AScheduler/License/SchedulerLicense.dat` | `<LicensePath>/Data/AScheduler/License/SchedulerLicense.dat</LicensePath>` |
| Scheduler | `/license-mount/AScheduler.license` | `/Data/License/AScheduler.license` | `"LicenseFileLocation": "/Data/License/AScheduler.license"` |

## Verification Steps

### 1. Check Pod Events
```bash
kubectl describe pod [POD-NAME] -n [NAMESPACE]
```
Look for mount-related errors in the Events section.

### 2. Verify Volume Mounts
```bash
kubectl get pod [POD-NAME] -n [NAMESPACE] -o yaml
```
Check that volumeMounts don't have conflicting paths.

### 3. Debug Container Logs
```bash
kubectl logs [POD-NAME] -n [NAMESPACE]
```
Entrypoint scripts now include debugging output for license file operations.

### 4. Exec into Container (if running)
```bash
kubectl exec -it [POD-NAME] -n [NAMESPACE] -- bash
ls -la /license-mount/
ls -la /Data/AScheduler/License/  # Engine
ls -la /Data/License/                 # Scheduler
```

## Common Pitfalls to Avoid

1. **Never mount files into existing mount point directories**
   - ConfigMaps create mount points that occupy entire directories
   - Individual file mounts into those directories will fail

2. **Don't assume license data format**
   - Engine uses binary copy (file already decoded)
   - Scheduler also uses binary copy (not base64 decode)
   - Verify your Secret contains the correct data format

3. **Check destination directory creation**
   - Always create destination directories before copying
   - Use `mkdir -p` to avoid errors if directories exist

4. **Validate configuration paths**
   - Ensure application configs point to final file locations
   - Path mismatches cause runtime application failures

## Troubleshooting Commands

### Pod Won't Start - Mount Issues
```bash
kubectl get events --sort-by=.metadata.creationTimestamp -n [NAMESPACE]
kubectl describe pod [POD-NAME] -n [NAMESPACE]
```

### Application Can't Find License
```bash
kubectl logs [POD-NAME] -n [NAMESPACE]
kubectl exec [POD-NAME] -n [NAMESPACE] -- find /Data -name "*license*" -type f
```

### Secret Content Verification
```bash
kubectl get secret [SECRET-NAME] -n [NAMESPACE] -o yaml
# Check that data contains the expected keys
```

## Prevention Strategy

1. **Design principle**: Keep ConfigMaps and Secrets in separate mount paths
2. **Testing**: Always test volume mounts in development before production
3. **Documentation**: Clearly document the file journey from values to application
4. **Monitoring**: Add debugging output to entrypoint scripts for troubleshooting

This separation strategy eliminates mount conflicts while maintaining secure license file handling through the Kubernetes Secret mechanism.