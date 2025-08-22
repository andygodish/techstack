---
tags: [JG, eks, kubernetes, licensing, flexnet, airgapped, zarf, troubleshooting, deployment, configuration]
---

# JG EKS Deployment Troubleshooting Summary

## Overview
Documentation of licensing and deployment issues encountered with the jg application deployment to an airgapped EKS cluster using Zarf.

## Application Architecture
The jg application consists of three main components:
1. **STK Pod** - Fetches licenses from remote EC2 instance
2. **Engine Pod** - Requires FlexNet license for `stk_scheduler` feature
3. **Scheduler Pod** - Requires `AstroScheduler.license` application license

## Issues Identified

### 1. Engine Pod - FlexNet License Error

**Error Symptoms:**
```
ERROR Engine - No such feature exists.
Feature:       stk_scheduler
License path:  1055@[INTERNAL-IP]:
FlexNet Licensing error:-5,147.  System Error: 115 "Operation now in progress"
```

**Root Cause Analysis:**
- ✅ Network connectivity confirmed: License server at `[INTERNAL-IP]:1055` is reachable
- ✅ License file `SchedulerLicense.dat` (772 bytes) successfully mounted from Secret
- ❌ FlexNet server doesn't provide `stk_scheduler` feature OR license file content mismatch

**Environment Variables:**
```yaml
- name: ANSYSLMD_LICENSE_FILE
  value: "1055@[INTERNAL-IP]"
```

**Configuration Path Mismatch:**

- Engine config expects: `/home/ubuntu/STKScheduler/Config/SchedulerLicense.dat`
- Actual mount location: `/Data/AstroScheduler/License/SchedulerLicense.dat`

### 2. Scheduler Pod - Missing License File

**Error Symptoms:**
```
ERROR [COMPANY].SelfHost.Program - License is Not Found
License file not found in ConfigMap
```

**Root Cause Analysis:**
- ❌ **CRITICAL YAML Syntax Error** in Helm template:
```yaml
# BROKEN - Missing indentation
- name: scheduler-license
  secret:
  secretName: [SECRET-NAME]

# CORRECT - Proper indentation  
- name: scheduler-license
  secret:
    secretName: [SECRET-NAME]
    defaultMode: 420
```

**Impact:** Invalid YAML caused Kubernetes to default to `emptyDir: {}` instead of mounting the license Secret.

**Expected License Location:**
```json
"LicenseFileLocation": "/Data/License/AstroScheduler.license"
```

### 3. Pod Crash Loop Behavior

**Symptoms:**
- Both engine and scheduler pods crash immediately upon startup
- No time available for `kubectl exec` debugging
- Pods restart continuously with same errors

**Debugging Limitations:**
- Standard troubleshooting methods (exec into pod) not viable
- Must rely on pod logs and static configuration analysis

## Network Connectivity Verification

**Test Results from Debug Pod:**
```bash
# License server connectivity test
nc -zv [INTERNAL-IP] 1055
# Result: [INTERNAL-IP] ([INTERNAL-IP]:1055) open

# Telnet test
telnet [INTERNAL-IP] 1055
# Result: Connected to [INTERNAL-IP], Connection closed by foreign host
```

**Conclusion:** Network path to license server is functional.

## Configuration Analysis

### Engine Pod Deployment
**Volume Mounts:**
```yaml
volumeMounts:
- mountPath: /Data/AstroScheduler/License/SchedulerLicense.dat
  name: license-secret
  readOnly: true
  subPath: SchedulerLicense.dat

volumes:
- name: license-secret
  secret:
    secretName: [ENGINE-SECRET-NAME]
```

**Status:** ✅ Correctly configured

### Scheduler Pod Deployment (FIXED)
**Original (Broken):**
```yaml
volumes:
- name: scheduler-license
  emptyDir: {}  # ← Caused by YAML syntax error
```

**Fixed:**
```yaml
volumes:
- name: scheduler-license
  secret:
    secretName: [SCHEDULER-SECRET-NAME]
    defaultMode: 420
```

## License File Analysis Required

**Engine License (`SchedulerLicense.dat`):**
- Size: 772 bytes
- Base64 encoded in Helm values
- May not contain required `stk_scheduler` feature

**Scheduler License (`AstroScheduler.license`):**
- Base64 encoded in Helm values  
- Decoded by entrypoint script during pod initialization

**Next Steps for License Verification:**
1. Decode base64 license values from Helm configuration
2. Verify license server actually serves `stk_scheduler` feature
3. Check license file format compatibility
4. Validate license expiration dates

## Airgapped Environment Considerations

**Zarf Configuration:**
- Registry: `[REGISTRY-URL]/[ORGANIZATION]/[PROJECT]/[IMAGE]:[TAG]`
- All images pulled through local registry
- Network policies may affect license server connectivity

**Debug Container Used:**
```
[REGISTRY-URL]/[ORGANIZATION]/[PROJECT]/busybox:[TAG]
```

## Resolution Strategies

### Immediate Fixes Applied
1. ✅ Fixed YAML syntax error in scheduler deployment template
2. ❌ License path configuration change had no effect (reverted)

### Remaining Actions
1. **License Content Verification**: Examine actual license file contents
2. **License Server Audit**: Verify features available on FlexNet server
3. **Feature Mapping**: Confirm `stk_scheduler` feature exists and is accessible
4. **Base64 Decoding**: Validate license file integrity after decoding

## Environment Details

**Kubernetes Platform:** Amazon EKS (Airgapped)
**Package Manager:** Zarf
**Namespace:** `[NAMESPACE]`
**Node Affinity:** `shared-storage` nodes for RWO volume access

**License Server:**
- Host: `[INTERNAL-IP]`
- Port: `1055`
- Protocol: FlexNet License Manager

## Status
**Current State:** Issues partially identified, YAML syntax fixed, pods still crash-looping
**Next Priority:** License content verification and FlexNet server feature audit
**Deployment Status:** Non-functional due to licensing issues