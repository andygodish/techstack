---
tags: [istio, mtls, kubernetes, ambient-mode, security, peerauthentication, tls, testing, configuration, troubleshooting]
---

# Istio mTLS Configuration and Testing Overview

## 1. Summary

This document records a discussion and testing walkthrough covering Istio mutual TLS (mTLS) configuration, PeerAuthentication behavior, and practical testing methods using `curl` under both plaintext and encrypted traffic conditions.

---

## 2. Istio mTLS Defaults

- mTLS is **not enabled by default** in Istio.  
- Default PeerAuthentication mode is **PERMISSIVE**, meaning workloads accept both plaintext and mTLS connections.  
- To enforce encryption, set mesh-wide or namespace-level PeerAuthentication to **STRICT** mode.

Example mesh-wide strict policy:

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT
```

## 3. PeerAuthentication Hierarchy

PeerAuthentication applies at three levels:

| Level | Scope | Override Behavior |
|--------|--------|------------------|
| Mesh-wide | Defined in `istio-system` | Base policy for entire mesh |
| Namespace | Defined per namespace | Overrides mesh-wide defaults |
| Workload | Uses selector | Overrides both mesh and namespace |

In this case:

- The mesh-wide policy is set to **STRICT**, enforcing mTLS globally.
- Namespace-level PeerAuthentications that also use STRICT are **redundant**.  
- A workload policy adds a **port-level PERMISSIVE** exception.

## 4. Port-Level mTLS Exception

Example (sanitized):

```yaml
apiVersion: security.istio.io/v1
kind: PeerAuthentication
metadata:
  name: permissive-webhook
  namespace: [NAMESPACE]
spec:
  mtls:
    mode: STRICT
  portLevelMtls:
    "3000":
      mode: PERMISSIVE
  selector:
    matchLabels:
      app: [WORKLOAD-LABEL]
```

Meaning
  •All ports require mTLS (STRICT) except port 3000.
  •Port 3000 allows both mTLS and plaintext connections (PERMISSIVE).
  •Typically used when an external webhook or controller needs non-mTLS access.

## 5. Traffic Direction and Behavior

- PeerAuthentication affects **ingress (server-side)** only.  
- Outbound (egress) traffic is governed by **DestinationRules** and the target’s PeerAuthentication policy.  
- Example: port 3000 on `[WORKLOAD-LABEL]` can receive plaintext, but outbound traffic from that pod still uses mTLS when required.

## 6. Istio Ambient Mode Behavior

In **ambient mode**, traffic flows through **ztunnels** using **HBONE (HTTP-based overlay mTLS)**:

- ztunnels handle mutual authentication and encryption.
- When a PERMISSIVE port is defined, ztunnel decrypts and delivers plaintext to that pod port.
- The connection remains **encrypted between ztunnels** but **plaintext inside the node** to the pod.

## 7. Testing Methodology

### Plaintext Request (non-mesh)

```bash
kubectl exec -n [NON-MESH-NS] curl-client -- \
  curl -si http://[SERVICE].[NAMESPACE].svc.cluster.local:3000/health
```

```bash
kubectl exec -n [MESH-NS] curl-client -- \
  curl -si http://[SERVICE].[NAMESPACE].svc.cluster.local:3000/health
```

```bash
kubectl exec -n [NS] curl-client -- \
  curl -skI https://[SERVICE].[NAMESPACE].svc.cluster.local:3000/health
```

| Test              | Layer         | Purpose                              |
|-------------------|---------------|--------------------------------------|
| HTTP              | None          | Validate plaintext on PERMISSIVE port |
| HTTP (mesh ambient) | HBONE mTLS   | Confirm ztunnel encryption            |
| HTTPS             | App-layer TLS | Verify if pod expects HTTPS           |

## 8. Common Curl Exit Codes

| Code | Meaning | Likely Cause |
|------|----------|--------------|
| 6 | Could not resolve host | Wrong Service name or DNS issue |
| 52 | Empty reply from server | Wrong protocol or port, no listener |
| 56 | TLS handshake failure | HTTP sent to HTTPS port or mTLS mismatch |

## 9. Concept Summary

| Concept | Description |
|----------|--------------|
| Plain-text request | Unencrypted HTTP request (no TLS) |
| Encrypted request | App-level HTTPS or mesh-level HBONE mTLS |
| PERMISSIVE | Accepts both plaintext and mTLS |
| STRICT | Accepts only mTLS |
| Ambient mTLS | Encryption handled by ztunnels between nodes |

## 10. Validation Commands

| Purpose | Command |
|----------|----------|
| Verify PeerAuthentication | `kubectl get peerauthentication -A` |
| Check mTLS status | `istioctl authn tls-check <pod>.<namespace>` |
| Inspect ztunnel config | `istioctl ztunnel-config workloads -n [NAMESPACE]` |
| View ztunnel logs | `kubectl logs -n istio-system -l app=ztunnel` |

## 11. Key Takeaways

- Mesh-wide **STRICT** mode enforces mTLS globally.  
- **PERMISSIVE** mode allows flexibility for onboarding and external access.  
- **PeerAuthentication** controls only **ingress**, not egress.  
- In **ambient mode**, ztunnels always encrypt between nodes.  
- Application HTTPS and mesh mTLS operate independently.
