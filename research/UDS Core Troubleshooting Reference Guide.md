---
tags: [uds-core, kubernetes, troubleshooting, istio, security, service-mesh, pepr, keycloak, monitoring]
---

# UDS Core Troubleshooting Reference Guide

UDS core is a collection of functional layers build into separate packages that are logically grouped together based on their functionality within the platform. Each functional layer is just a zarf package that is published separately. A "UDS bundle" is just a collection of these package that can also be published as a single compressed file for easy transport and installation. 

A UDS Core functional layer will typically be defined in a series of Zarf package definitions layered ontop of one another.

Layer 1 defines the functional layer itself. The logging layer may contain two specific services, Loki & Vector, represented as components in the Zarf package definition, 

```yaml
kind: ZarfPackageConfig
metadata:
  name: core-identity-authorization
components:
  - name: keycloak
    required: true
    import:
      path: ../../src/keycloak
  - name: authservice
    required: true
    import:
      path: ../../src/authservice
```

These are just local references to other directories within the UDS Core repository, pointing to Layer 2, the flavor layer (my terminology). Here is just another Zarf package yaml definition that differentiates between flavors (upstream, registry1, unicorn) and defines the OCI container images + registry paths specific to that flavor, 

```yaml
kind: ZarfPackageConfig
metadata:
  name: uds-core-loki
components:
  - name: loki
    required: true
    description: "Install Loki using upstream (docker) images"
    only:
      flavor: "upstream"
    import:
      path: common
    charts:
      - name: loki
        valuesFiles:
          - ./values/upstream-values.yaml
    images:
      - docker.io/grafana/loki:3.5.3
  - name: loki
    required: true
    description: "Install Loki using registry1 images"
    only:
      flavor: "registry1"
    import:
      path: common
    charts:
      - name: loki
        valuesFiles:
          - ./values/registry1-values.yaml
    images:
      - registry1.dso.mil/ironbank/opensource/grafana/loki:3.5.3

  - name: loki
    required: true
    description: "Install Loki using Rapidfort images"
    only:
      flavor: "unicorn"
    import:
      path: common
    charts:
      - name: loki
        valuesFiles:
          - ./values/unicorn-values.yaml
    images:
      - quay.io/rfcurated/grafana/loki:3.5.3-jammy-fips-rfcurated-rfhardened
```

This layer usually provides helm chart value overrides specific to the container images found in that flavors registry. It also imports helm charts from Layer 3, the common layer. This final layer typcially pulls in two helm charts, the upstream chart from the original application maintainer, and a UDS Core specific chart configuration chart (uds-*-config) that provides additional configuration needed to run the application within the UDS Core platform by deploying package CRDs defined by the UDS Operator. So we have 3 layers of zarf packages, 

```yaml
kind: ZarfPackageConfig
metadata:
  name: uds-core-loki-common
components:
  - name: loki
    required: true
    charts:
      - name: uds-loki-config
        namespace: loki
        version: 0.2.0
        localPath: ../chart
      - name: loki
        url: https://grafana.github.io/helm-charts/ # upstream chart
        version: 6.36.1
        namespace: loki
        valuesFiles:
          - ../values/values.yaml # opinionated overrides for UDS Core
```

If a "valuesFiles:" array is not definied in this 3rd layer package, then the default values.yaml file from the upstream chart will be used. Overrides in this layer represent the opinionated defaults for running the application within UDS Core. Note, in layer 2, the "charts:" array is calling the names of the charts defined in layer 3. 

All applications integrated into UDS Core are done so in a similar manner. 

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