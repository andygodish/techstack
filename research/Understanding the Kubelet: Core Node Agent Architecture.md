---
tags: [kubelet, kubernetes, cri, containerd, node-agent, static-pods, health-checks, container-runtime, architecture]
---

# Understanding the Kubelet: Core Node Agent Architecture

## Overview

The kubelet is the primary node agent in Kubernetes, responsible for managing containers and communicating with the control plane. Understanding kubelet architecture and operation is fundamental to Kubernetes troubleshooting and system comprehension.

## Kubelet Fundamentals

### What is the Kubelet?

The kubelet is a **system service** (not a pod) that runs on every Kubernetes node, including both worker and control plane nodes. It serves as the bridge between the Kubernetes control plane and the container runtime.

**Key Responsibilities:**
- Container lifecycle management
- Pod specification enforcement
- Health monitoring and reporting
- Static pod management (control plane nodes)
- Node status reporting to API server

### System Service Architecture

**Why kubelet runs as a system service:**
- Bootstrap problem: Cannot manage pods without something to manage the pod manager
- System-level access required for container runtime interaction
- Direct host integration needed for networking and storage operations
- Reliability: Must survive container runtime failures

**Service Management:**
```bash
# Traditional Linux distributions
systemctl status kubelet
journalctl -u kubelet -f

# Bottlerocket OS (AWS optimized)
# Managed by Bottlerocket's init system
```

## Kubelet on All Node Types

### Control Plane Nodes

**Components managed by kubelet:**
- **Static pods** defined in `/etc/kubernetes/manifests/`
  - kube-apiserver
  - kube-controller-manager
  - kube-scheduler
  - etcd

**Static pod characteristics:**
- Managed directly by kubelet, not API server
- Automatically restarted on failure
- Survive API server outages
- Manifests watched via filesystem

### Worker Nodes

**Components managed by kubelet:**
- Regular pods scheduled by control plane
- DaemonSet pods (kube-proxy, CNI agents, monitoring)
- No static pods (typically)

**Note:** kubelet itself never appears as a pod in `kubectl get pods` output on any node type.

## Container Runtime Integration

### Container Runtime Interface (CRI)

The kubelet communicates with container runtimes through the standardized CRI gRPC API, not direct command execution.

**Communication Flow:**
```
kubelet → CRI gRPC calls → container runtime → actual containers
```

**Standard CRI Operations:**
- `RunPodSandbox()` - Creates pod network/storage namespace
- `CreateContainer()` - Creates container from image specification
- `StartContainer()` - Starts container process
- `StopContainer()` - Terminates running container
- `RemoveContainer()` - Cleans up stopped container

### Supported Container Runtimes

**containerd** (Most Common)
- Native CRI implementation
- Lightweight, focused on container execution
- Used by Docker Desktop and major cloud providers
- Direct gRPC communication with kubelet

**CRI-O**
- Built specifically for Kubernetes CRI compliance
- Implements only CRI-required functionality
- Common in OpenShift environments

**Docker Engine** (Legacy)
- Requires cri-dockerd translation layer
- Docker doesn't natively speak CRI
- Translation layer converts CRI calls to Docker API calls

### Runtime Detection

```bash
# Check node container runtime
kubectl get nodes -o wide
# Look at CONTAINER-RUNTIME column

# Direct runtime interaction (on node)
crictl version  # Shows kubelet and runtime versions
crictl ps       # List containers via CRI
crictl pods     # List pod sandboxes
```

## Health Monitoring Architecture

### Container Health Checks

The kubelet implements three probe types defined in pod specifications:

**Liveness Probes**
- Determines if container is running properly
- Failure triggers container restart according to restart policy
- Prevents "zombie" containers that appear running but are non-functional

**Readiness Probes**
- Determines if container is ready to serve traffic
- Failure removes pod from service endpoints
- Container continues running, not restarted

**Startup Probes**
- Provides slow-starting containers initialization time
- Prevents premature liveness probe failures
- Particularly important for applications with long startup sequences

**Probe Methods:**
- HTTP GET requests to specified endpoints
- TCP socket connection attempts
- Command execution inside container

### Static Pod Health Management

For control plane components, the kubelet provides critical self-healing:

**Monitoring Process:**
- Continuous filesystem watching of `/etc/kubernetes/manifests/`
- Automatic detection of manifest changes
- Container restart on health check failures
- Status reporting to API server (when available)

**Self-Healing Capability:**
- Functions even during API server outages
- Maintains control plane availability
- Critical for cluster recovery scenarios

### Node-Level Health Reporting

**Node Conditions Reported:**
- `Ready` - Node healthy and accepting pods
- `MemoryPressure` - Node experiencing memory constraints
- `DiskPressure` - Node experiencing storage pressure
- `PIDPressure` - Node has too many processes running
- `NetworkUnavailable` - Node network incorrectly configured

**Resource Monitoring:**
- CPU, memory, and disk usage tracking
- Provides data for scheduling decisions
- Enables resource-based pod eviction

**Implementation Location:**
Source code in `pkg/kubelet/prober/` contains probe manager orchestrating all health checking operations.

## Pod Lifecycle Management

### Pod Creation Flow

1. **API Server** stores pod specification in etcd
2. **Scheduler** assigns pod to specific node
3. **kubelet** detects pod assignment through API server watch
4. **kubelet** calls container runtime via CRI
5. **Container runtime** pulls images and creates containers
6. **kubelet** monitors container health and reports status

### Container Runtime Interaction

Instead of executing shell commands like `docker run`, the kubelet makes programmatic CRI calls:

```go
// Example CRI interaction (pseudo-code)
sandbox := runtime.RunPodSandbox(podConfig)
container := runtime.CreateContainer(sandbox, containerConfig, podConfig)
runtime.StartContainer(container)
```

### Networking and Storage

**Pod Sandbox Creation:**
- Network namespace establishment
- Storage volume mounting
- Security context application

**Container Attachment:**
- Containers join pod sandbox network
- Shared storage volumes mounted
- Process isolation maintained

## Source Code Architecture

### Key Directories

**Main kubelet code:**
- `pkg/kubelet/` - Core kubelet implementation
- `pkg/kubelet/kuberuntime/` - CRI integration layer
- `pkg/kubelet/prober/` - Health checking system
- `pkg/kubelet/lifecycle/` - Container lifecycle management

**Runtime Management:**
- `kubeGenericRuntimeManager` orchestrates CRI calls
- Abstracts container runtime specifics from core kubelet logic
- Handles image management and container state tracking

### Static Pod Implementation

**File System Monitoring:**
- kubelet watches `/etc/kubernetes/manifests/` directory
- Manifest changes trigger pod reconciliation
- No API server dependency for static pod management

**Reconciliation Loop:**
- Continuous comparison of desired vs. actual state
- Automatic correction of configuration drift
- Independent operation during control plane failures

## Troubleshooting Applications

### Common kubelet Issues

**Pod Stuck in Pending:**
- Check kubelet logs for scheduling constraints
- Verify resource availability on target node
- Confirm container runtime responsiveness

**Container Restart Loops:**
- Examine liveness probe configuration
- Review container logs for startup failures
- Check resource limits and requests

**Network Connectivity Problems:**
- Verify CNI plugin functionality
- Check kube-proxy DaemonSet status
- Examine pod sandbox creation logs

### Diagnostic Commands

```bash
# kubelet service status
systemctl status kubelet
journalctl -u kubelet --since "1 hour ago"

# Container runtime interaction
crictl ps --state=running
crictl inspect [CONTAINER-ID]
crictl logs [CONTAINER-ID]

# Pod-level debugging
kubectl describe pod [POD-NAME]
kubectl logs [POD-NAME] --previous
```

## Key Architectural Insights

### Universal Presence
- Every node runs kubelet, regardless of role
- Control plane and worker nodes use identical kubelet binary
- Difference lies in static pod configuration, not kubelet code

### Runtime Abstraction
- CRI provides clean abstraction between kubelet and container runtimes
- Same kubelet code works with different runtime implementations
- Runtime switching possible without kubelet changes

### Self-Healing Foundation
- kubelet health checking enables Kubernetes self-healing capabilities
- Static pod management ensures control plane resilience
- Node-level monitoring provides cluster-wide health visibility

### System Integration
- Deep host system integration required for container management
- Privileged operations necessary for networking and storage
- System service model provides necessary reliability and access