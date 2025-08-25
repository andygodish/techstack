---
tags: [gitlab, irsa, s3, eks, aws-govcloud, authentication, troubleshooting, helm, kubernetes, rbac]
---

# GitLab Runner IRSA Service Account Configuration Issue

## Problem Summary

GitLab Runner jobs were failing with cross-namespace permissions errors when trying to access S3 resources through IRSA (IAM Roles for Service Accounts). The runner pod was unable to create secrets in the target job namespace due to missing service account configuration.

## Error Symptoms

```
ERROR: Job failed (system failure): prepare environment: setting up credentials: secrets is forbidden: 
User "system:serviceaccount:[RUNNER-NAMESPACE]:[SERVICE-ACCOUNT]" cannot create resource "secrets" 
in API group "" in the namespace "[JOB-NAMESPACE]"
```

## Root Cause Analysis

### Architecture Overview
- **Runner Pod**: Runs in `[RUNNER-NAMESPACE]` using service account `[SERVICE-ACCOUNT-NAME]`
- **Job Pods**: Created in `[JOB-NAMESPACE]` for pipeline execution
- **IRSA Configuration**: Service account with AWS IAM role annotation exists in `[JOB-NAMESPACE]`

### The Issue
1. GitLab upgrade/rollback created a new service account (`[SERVICE-ACCOUNT-NAME]`) in the runner namespace
2. Runner configuration was set to create job pods in a different namespace (`[JOB-NAMESPACE]`)
3. Job pods needed to use the IRSA-enabled service account for S3 access
4. Runner configuration didn't specify which service account job pods should use
5. Cross-namespace RBAC permissions were missing

## Investigation Steps

### 1. Identify Service Account Configuration
```bash
# Check which service account the runner deployment uses
kubectl get deployment [RUNNER-DEPLOYMENT] -n [RUNNER-NAMESPACE] -o yaml | grep -A 5 -B 5 serviceAccount

# Check current Helm values
helm get values [RUNNER-RELEASE] -n [RUNNER-NAMESPACE]
```

### 2. Examine Runner Configuration
```bash
# Check the runner's ConfigMap for job namespace and service account settings
kubectl get configmap [RUNNER-CONFIGMAP] -n [RUNNER-NAMESPACE] -o yaml
```

### 3. Verify IRSA Setup
```bash
# Check for IRSA-enabled service accounts
kubectl get serviceaccount -n [JOB-NAMESPACE] -o yaml | grep -A 3 eks.amazonaws.com/role-arn
```

## Solution Implementation

### Step 1: Configure Job Pod Service Account

Edit the GitLab Runner ConfigMap to specify which service account job pods should use:

```bash
kubectl edit configmap [RUNNER-CONFIGMAP] -n [RUNNER-NAMESPACE]
```

In the `config.template.toml` section, add the service account specification:

```toml
[runners.kubernetes]
  privileged = true
  namespace = "[JOB-NAMESPACE]"
  service_account = "[IRSA-SERVICE-ACCOUNT]"  # Add this line
  helper_image = "[HELPER-IMAGE]"
  image = "[JOB-IMAGE]"
```

### Step 2: Add Cross-Namespace RBAC Permissions

Create ClusterRole and binding for cross-namespace operations:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: gitlab-runner-cross-namespace
rules:
- apiGroups: [""]
  resources: ["secrets", "pods", "pods/exec", "pods/attach", "pods/log", "configmaps"]
  verbs: ["list", "get", "create", "patch", "delete", "watch", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: gitlab-runner-cross-namespace-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: gitlab-runner-cross-namespace
subjects:
- kind: ServiceAccount
  name: [SERVICE-ACCOUNT-NAME]
  namespace: [RUNNER-NAMESPACE]
```

### Step 3: Restart Runner
```bash
kubectl rollout restart deployment [RUNNER-DEPLOYMENT] -n [RUNNER-NAMESPACE]
```

## Permanent Solution (Helm Values)

To make this configuration persistent, update your Helm values file:

```yaml
rbac:
  create: true
  rules:
  - apiGroups: [""]
    resources: ["secrets", "pods", "pods/exec", "pods/attach", "pods/log", "configmaps"]
    verbs: ["list", "get", "create", "patch", "delete", "watch", "update"]

runners:
  config: |
    [[runners]]
      [runners.kubernetes]
        namespace = "[JOB-NAMESPACE]"
        service_account = "[IRSA-SERVICE-ACCOUNT]"
        # ... other configuration
```

## Verification

### 1. Check Permissions
```bash
# Verify the service account can create/update secrets in target namespace
kubectl auth can-i create secrets --as=system:serviceaccount:[RUNNER-NAMESPACE]:[SERVICE-ACCOUNT-NAME] -n [JOB-NAMESPACE]
kubectl auth can-i update secrets --as=system:serviceaccount:[RUNNER-NAMESPACE]:[SERVICE-ACCOUNT-NAME] -n [JOB-NAMESPACE]
```

### 2. Test Pipeline
Run a pipeline that requires S3 access to confirm:
- No "secrets is forbidden" errors
- S3 operations complete successfully
- Job pods are created and cleaned up properly

## Key Insights

### Service Account Architecture
- **Runner pods** need permissions to manage resources in job namespaces
- **Job pods** need IRSA configuration for AWS service access
- **Cross-namespace operations** require explicit ClusterRole permissions

### Common Pitfalls
- Assuming same-namespace service accounts work for cross-namespace operations
- Missing `update` verb in RBAC rules (needed for ownerReferences)
- Forgetting to specify job pod service account in runner configuration
- IRSA service accounts in wrong namespace for job execution

### Prevention
- Always verify RBAC permissions when deploying across namespaces
- Include comprehensive verbs in ClusterRole rules
- Explicitly configure service accounts for job pods
- Test cross-namespace operations after GitLab Runner upgrades

## Related Documentation
- [GitLab Runner Kubernetes Executor](https://docs.gitlab.com/runner/executors/kubernetes.html)
- [AWS IAM Roles for Service Accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [Kubernetes RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

## Troubleshooting Commands

```bash
# Check runner pod logs
kubectl logs -n [RUNNER-NAMESPACE] deployment/[RUNNER-DEPLOYMENT]

# Verify service account annotations
kubectl get serviceaccount [SERVICE-ACCOUNT] -n [NAMESPACE] -o yaml

# Check RBAC permissions
kubectl auth can-i [VERB] [RESOURCE] --as=system:serviceaccount:[NAMESPACE]:[SERVICE-ACCOUNT] -n [TARGET-NAMESPACE]

# Review runner configuration
kubectl get configmap [RUNNER-CONFIGMAP] -n [RUNNER-NAMESPACE] -o yaml
```