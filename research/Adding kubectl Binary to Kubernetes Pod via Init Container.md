---
tags: [kubernetes, kubectl, init-container, helm, cronjob, rbac, deployment, eks, airgapped-registry, troubleshooting]
---

# Adding kubectl Binary to Kubernetes Pod via Init Container

## Overview

This document describes how to add kubectl functionality to a Kubernetes pod that doesn't have the kubectl binary installed, using an init container pattern to copy the binary from an airgapped container registry.

## Problem Statement

A service running in a Kubernetes pod on an EKS cluster needed kubectl access to create and manage CronJobs, but the primary container image did not include the kubectl binary. The solution required using an available kubectl image from an airgapped container registry.

## Solution Architecture

The solution uses an init container to copy the kubectl binary to a shared volume that the main application container can access:

1. **Init Container**: Runs first, copies kubectl binary from source image to shared volume
2. **Shared Volume**: `emptyDir` volume mounted in both containers
3. **Main Container**: Accesses kubectl via shared volume with updated PATH
4. **RBAC**: Custom ServiceAccount with permissions to manage CronJobs and Jobs

## Implementation Steps

### Step 1: Basic Init Container Pattern

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: [POD-NAME]
  namespace: [NAMESPACE]
spec:
  initContainers:
  - name: kubectl-provider
    image: [REGISTRY-URL]/kubectl:[TAG]
    command: ['sh', '-c']
    args:
    - |
      echo "Copying kubectl binary..."
      cp /usr/local/bin/kubectl /shared-bin/kubectl
      chmod +x /shared-bin/kubectl
      echo "kubectl copied successfully"
    volumeMounts:
    - name: kubectl-binary
      mountPath: /shared-bin
  
  containers:
  - name: main-service
    image: [REGISTRY-URL]/[APP-IMAGE]:[TAG]
    env:
    - name: PATH
      value: "/shared-bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    volumeMounts:
    - name: kubectl-binary
      mountPath: /shared-bin
  
  volumes:
  - name: kubectl-binary
    emptyDir: {}
```

### Step 2: RBAC Configuration

Create the necessary ServiceAccount and permissions:

```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: [SERVICE-NAME]-sa
  namespace: [NAMESPACE]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cronjob-manager
rules:
- apiGroups: ["batch"]
  resources: ["cronjobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: [SERVICE-NAME]-cronjob-manager
subjects:
- kind: ServiceAccount
  name: [SERVICE-NAME]-sa
  namespace: [NAMESPACE]
roleRef:
  kind: ClusterRole
  name: cronjob-manager
  apiGroup: rbac.authorization.k8s.io
```

### Step 3: Helm Template Implementation

For Helm-managed deployments, create these template files:

#### templates/scheduler-serviceaccount.yaml
```yaml
{{- if .Values.scheduler.kubectl.enabled }}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.scheduler.name }}-sa
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ .Values.scheduler.name }}
    app.kubernetes.io/name: {{ .Values.scheduler.name }}
    app.kubernetes.io/component: scheduler
{{- end }}
```

#### templates/scheduler-clusterrole.yaml
```yaml
{{- if .Values.scheduler.kubectl.enabled }}
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: {{ .Values.scheduler.name }}-cronjob-manager
  labels:
    app: {{ .Values.scheduler.name }}
    app.kubernetes.io/name: {{ .Values.scheduler.name }}
    app.kubernetes.io/component: scheduler
rules:
- apiGroups: ["batch"]
  resources: ["cronjobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
{{- end }}
```

#### templates/scheduler-clusterrolebinding.yaml
```yaml
{{- if .Values.scheduler.kubectl.enabled }}
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: {{ .Values.scheduler.name }}-cronjob-manager
  labels:
    app: {{ .Values.scheduler.name }}
    app.kubernetes.io/name: {{ .Values.scheduler.name }}
    app.kubernetes.io/component: scheduler
subjects:
- kind: ServiceAccount
  name: {{ .Values.scheduler.name }}-sa
  namespace: {{ .Release.Namespace }}
roleRef:
  kind: ClusterRole
  name: {{ .Values.scheduler.name }}-cronjob-manager
  apiGroup: rbac.authorization.k8s.io
{{- end }}
```

#### Updated Deployment Template
Key additions to the main deployment template:

```yaml
spec:
  template:
    spec:
      {{- if .Values.scheduler.kubectl.enabled }}
      serviceAccountName: {{ .Values.scheduler.name }}-sa
      
      initContainers:
      - name: kubectl-provider
        image: "{{ .Values.scheduler.kubectl.image.registry }}/{{ .Values.scheduler.kubectl.image.repository }}:{{ .Values.scheduler.kubectl.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        command: ['sh', '-c']
        args:
        - |
          echo "Copying kubectl binary from {{ .Values.scheduler.kubectl.binaryPath }} to /shared-bin/kubectl..."
          cp {{ .Values.scheduler.kubectl.binaryPath }} /shared-bin/kubectl
          chmod +x /shared-bin/kubectl
          echo "kubectl binary copied successfully"
        volumeMounts:
        - name: kubectl-binary
          mountPath: /shared-bin
        securityContext:
          runAsUser: 1000
          runAsGroup: 1000
      {{- end }}
      
      containers:
      - name: {{ .Values.scheduler.name }}
        # ... existing container config ...
        env:
        {{- if .Values.scheduler.kubectl.enabled }}
        - name: PATH
          value: "/shared-bin:/home/dotnet/.local/bin:/home/dotnet/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/dotnet/.dotnet/tools"
        {{- end }}
        # ... other env vars ...
        
        volumeMounts:
        {{- if .Values.scheduler.kubectl.enabled }}
        - name: kubectl-binary
          mountPath: /shared-bin
        {{- end }}
        # ... other volume mounts ...
      
      volumes:
      {{- if .Values.scheduler.kubectl.enabled }}
      - name: kubectl-binary
        emptyDir: {}
      {{- end }}
      # ... other volumes ...
```

#### values.yaml Configuration
```yaml
scheduler:
  kubectl:
    enabled: true
    binaryPath: "/usr/local/bin/kubectl"
    image:
      registry: "[REGISTRY-URL]"
      repository: "kubectl"
      tag: "1.33.4-jammy-scratch-fips"
```

## Testing and Validation

### 1. Verify Init Container Success
```bash
kubectl logs deployment/[DEPLOYMENT-NAME] -n [NAMESPACE] -c kubectl-provider
```

### 2. Test kubectl Access
```bash
kubectl exec -it deployment/[DEPLOYMENT-NAME] -n [NAMESPACE] -- kubectl version --client
```

### 3. Test CronJob Creation
```bash
kubectl exec -it deployment/[DEPLOYMENT-NAME] -n [NAMESPACE] -- kubectl create cronjob test-job --image=busybox --schedule="*/5 * * * *" -- echo "Hello World"
```

### 4. Test Cross-Namespace CronJob Triggering
```bash
# List existing CronJobs in another namespace
kubectl exec -it deployment/[DEPLOYMENT-NAME] -n [NAMESPACE] -- kubectl get cronjobs -n [OTHER-NAMESPACE]

# Trigger an existing CronJob
kubectl exec -it deployment/[DEPLOYMENT-NAME] -n [NAMESPACE] -- kubectl create job --from=cronjob/[CRONJOB-NAME] manual-trigger-$(date +%s) -n [OTHER-NAMESPACE]
```

## Key Considerations

### Security Context
- Ensure init container runs with same user/group as main container to avoid permission issues
- Use `runAsUser: 1000` and `runAsGroup: 1000` if main container runs as non-root

### PATH Management
- Preserve existing PATH components, especially for applications with specific binary requirements
- Place `/shared-bin` first in PATH for kubectl priority
- Include dotnet-specific paths for .NET applications

### RBAC Permissions
- Custom ServiceAccount only has explicitly granted permissions
- ClusterRole allows cross-namespace operations
- Permissions include CronJob, Job, and Pod resources for full workflow management

### Helm Template Best Practices
- Use conditional logic (`{{- if .Values.scheduler.kubectl.enabled }}`) for optional features
- Maintain consistent labeling across all resources
- Use proper octal notation for file permissions (`0755`, not `"0755"`)

## Troubleshooting

### Common Issues

1. **File Permission Errors**
   - Ensure octal notation without quotes: `defaultMode: 0755`
   - Check security context matches between init and main containers

2. **Volume Mount Issues**
   - Verify volume names match between definitions and mounts
   - Check that required ConfigMaps and Secrets exist

3. **RBAC Permission Denied**
   - Verify ServiceAccount is properly referenced in deployment
   - Check ClusterRoleBinding links correct ServiceAccount and ClusterRole
   - Confirm namespace matches in all RBAC resources

4. **Helm Template Not Updating**
   - Use `helm template` to verify generated YAML
   - Try `helm upgrade --force` to recreate resources
   - Check that conditional values are properly set

### Verification Commands
```bash
# Check Helm template output
helm template [RELEASE-NAME] ./helm/[CHART-NAME] -n [NAMESPACE]

# Check deployment status
kubectl rollout status deployment/[DEPLOYMENT-NAME] -n [NAMESPACE]

# Verify RBAC resources
kubectl get serviceaccount,clusterrole,clusterrolebinding -n [NAMESPACE]

# Check kubectl binary in container
kubectl exec -it deployment/[DEPLOYMENT-NAME] -n [NAMESPACE] -- ls -la /shared-bin/kubectl
```

## Benefits

- **Clean separation**: kubectl functionality is optional and configurable
- **Security**: Minimal required permissions with proper RBAC
- **Maintainable**: Helm templates allow easy enable/disable of functionality
- **Compatible**: Works with airgapped registries and custom security policies
- **Efficient**: Binary copied once per pod lifecycle via init container

This pattern is ideal for applications that need occasional kubectl access without rebuilding container images or compromising security.