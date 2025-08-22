---
tags: [uds-core, kubernetes, troubleshooting, istio, security, service-mesh, pepr, keycloak, monitoring]
---

# UDS Core Troubleshooting Reference Guide

## What is UDS Core?
UDS Core is a **secure baseline platform for cloud-native systems** in highly regulated environments. It's a collection of applications packaged as a single `Bundle` that provides:
- Service mesh security (Istio)
- Identity/authentication (Keycloak)  
- Policy enforcement (UDS Policy Engine)
- Monitoring/observability (Prometheus, Grafana, Loki)
- Backup/restore capabilities (Velero)

## Core Architecture Components

### UDS Operator
- Manages Package Custom Resources (CRs) and associated Kubernetes resources
- Handles NetworkPolicies, Istio VirtualServices, and AuthorizationPolicies
- Enables Istio sidecar injection and Ambient mode support
- **Key for troubleshooting**: Controls ingress/egress rules and service mesh configuration

### UDS Policy Engine (Pepr)
- **Mutating policies**: Enforces secure defaults (non-root users, dropped capabilities)
- **Validating policies**: Prevents insecure configurations (privileged pods, host namespaces)
- **Exemptions**: Can be granted via UDS Exemption CRs in `uds-policy-exemptions` namespace
- **Common issue**: Policy violations blocking pod creation/updates

### Service Mesh Modes
1. **Sidecar Mode** (traditional): Dedicated Envoy proxy per pod
2. **Ambient Mode** (newer): Node-level proxies + optional waypoint proxies
   - Lower resource overhead, simpler deployments
   - Layer 7 features require waypoint proxies
   - Default starting v0.43.0

## Security Model: "Deny by Default"

### Ingress Control
- **Default**: All ingress is denied
- **Enabled via**: `allow` and `expose` rules in Package CR
- **Gateways**: 
  - **Tenant Gateway**: End-user applications
  - **Admin Gateway**: Administrative applications
  - **Passthrough Gateway**: Applications handling own TLS

### Egress Control
- **Default**: Controlled via Istio
- **Enabled via**: `network.allow` with `remoteHost` and `port` in Package CR
- **Limitation**: Only works with sidecar mode (not ambient mode)
- **Creates**: ServiceEntry, Sidecar, VirtualService, Gateway resources

### Authorization Policies
- **ALLOW-based by default** - must write DENY rules separately
- **Evaluation order**: DENY policies first, then ALLOW policies
- **Best practice**: Use `remoteServiceAccount` for identity-based access

## Authentication & Authorization (SSO)

### Keycloak Integration
- **Auto-configuration**: UDS Operator creates Keycloak Clients automatically
- **Identity brokering**: Supports SAML, OAuth 2.0, OIDC external providers
- **Group-based access**: Controls app access via User Group membership
- **Session management**: Configurable timeouts and concurrent session limits

### Authservice Protection
- **Purpose**: Authentication for apps without native OIDC
- **Configuration**: Set `enableAuthserviceSelector` + label application pods
- **Use case**: Simple web UI protection scenarios

## Observability Stack

### Monitoring
- **Prometheus**: Metrics collection via ServiceMonitor/PodMonitor CRs
- **Grafana**: Dashboards auto-loaded from ConfigMaps with `grafana_dashboard: "1"` label
- **Special handling**: UDS Core manages Istio mTLS for Prometheus scraping

### Logging
- **Loki**: Log aggregation with object storage backend
- **Vector**: Daemonset for log collection from hosts
- **Configuration**: Schema-based index management

## Common Troubleshooting Scenarios

### Pod Startup Issues
1. **Policy violations**: Check UDS Policy Engine logs
2. **Network policies**: Verify allow rules in Package CR
3. **Service mesh**: Confirm sidecar injection or ambient mode config
4. **Resource constraints**: Check node resources and limits

### Connectivity Problems
1. **Ingress**: Verify `expose` rules and gateway configuration
2. **Egress**: Check `network.allow` rules (sidecar mode only)
3. **Service-to-service**: Confirm AuthorizationPolicies allow traffic
4. **DNS**: Validate Kubernetes DNS and service discovery

### Authentication Issues
1. **Keycloak client config**: Check UDS Operator logs for client creation
2. **Authservice**: Verify pod labeling and selector configuration
3. **Session timeouts**: Review realm vs client timeout settings
4. **Group membership**: Confirm user belongs to required Keycloak groups

### Resource Management
1. **Watch failures**: Check controller logs for Kubernetes API issues
2. **Secret updates**: Use `uds.dev/pod-reload: "true"` for automatic reloads
3. **Webhook dependencies**: Istiod/Pepr circular dependencies (rare in v0.50.0+)

## Key Troubleshooting Commands

```bash
# Check UDS Operator status
kubectl get pods -n uds-core

# View Package CRs
kubectl get packages -A

# Check policy exemptions
kubectl get udsexemptions -n uds-policy-exemptions

# Verify Istio service mesh
kubectl get vs,dr,se -A  # VirtualServices, DestinationRules, ServiceEntries

# Monitor authorization policies
kubectl get authorizationpolicies -A

# Check Keycloak client configuration
kubectl get keycloakclient -A
```

## Environment Prerequisites
- **Kubernetes**: Any CNCF conformant distribution (K3s, EKS, AKS, RKE2)
- **Storage**: Default storage class required
- **CNI**: Must support NetworkPolicies
- **Load balancer**: Dynamic provisioning for Istio ingress
- **Kernel modules**: Required for Istio functionality

## Important Notes for Troubleshooting
- **Sequential upgrades recommended**: Don't skip minor versions
- **Namespace ignoring available**: Use cautiously - reduces security
- **Ambient mode transition**: Auto-occurs during upgrades starting v0.43.0
- **Resource requirements**: Components can be tuned for HA or resource optimization

## Getting Help
- Check UDS Operator logs for Package CR processing issues
- Review Pepr logs for policy violations
- Verify Istio configuration for networking problems
- Examine Keycloak logs for authentication failures