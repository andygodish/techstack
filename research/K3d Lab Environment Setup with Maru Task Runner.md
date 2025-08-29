---
tags: [k3d, zarf, uds, kubernetes, maru, task-runner, automation, deployment, configuration, development]
---

# K3d Lab Environment Setup with Maru Task Runner

## Overview

This document details the setup of a K3d-based development environment using the upstream UDS K3d Zarf package with declarative configuration overrides via Zarf config files and Maru task automation.

## Architecture Approach

### Package Strategy Decision
After exploring multiple approaches for customizing the upstream UDS K3d package, we determined that **declarative Zarf config files** provide the optimal balance of maintainability and functionality over creating custom Zarf packages.

**Approaches Evaluated:**
- **Custom Zarf Package Creation**: Requires maintaining component definitions and handling skeleton package imports (not available from upstream)
- **Component Import Strategy**: Limited by upstream package structure and maintenance overhead
- **Declarative Config Files**: Leverages Zarf's native configuration system without package duplication

### Configuration Architecture

The solution uses Zarf TOML config files to override package variables at deployment time:

```
[REPOSITORY-ROOT]/
├── tasks.yaml                    # Maru task definitions
├── zarf-config.toml             # Default lab configuration
├── configs/
│   ├── zarf-config-staging.toml # Staging environment
│   └── zarf-config-production.toml # Production-like settings
```

## Core Components

### UDS K3d Package Structure
The upstream package (`ghcr.io/defenseunicorns/packages/uds-k3d:0.16.0`) contains:

1. **destroy-cluster**: Removes existing K3d clusters
2. **create-cluster**: Creates new K3d cluster with K3s
3. **uds-dev-stack**: Installs MetalLB, NGINX, Minio, and supporting infrastructure

### Configurable Variables
Package-level variables available for override:

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLUSTER_NAME` | `uds` | K3d cluster identifier |
| `DOMAIN` | `uds.dev` | Base domain for services |
| `ADMIN_DOMAIN` | `admin.DOMAIN` | Administrative services domain |
| `K3D_API_PORT` | `6550` | Kubernetes API server port |
| `K3D_HTTP_PORT` | `80` | HTTP ingress port mapping |
| `K3D_HTTPS_PORT` | `443` | HTTPS ingress port mapping |
| `K3D_DEBUG` | `false` | Enable debug mode |
| `K3D_IMAGE` | `rancher/k3s:v1.32.5-k3s1` | K3s container image |
| `K3D_ULIMIT_NOFILE` | `1048576:1048576` | File descriptor limits |
| `K3D_EXTRA_ARGS` | `""` | Additional k3d arguments |
| `NGINX_EXTRA_PORTS` | `[]` | Extra port mappings for NGINX |
| `COREDNS_OVERRIDES` | - | CoreDNS rewrite rules |

### Component-Level Variable Exposure
The `COREDNS_OVERRIDES` variable demonstrates successful component-level configuration through chart variables:

```yaml
charts:
  - name: uds-dev-stack
    variables:
      - name: COREDNS_OVERRIDES
        path: coreDnsOverrides
```

This creates a pathway for package-level variables to reach component chart values.

## Configuration Implementation

### Primary Lab Config (`zarf-config.toml`)
```toml
log_format = 'console'
log_level = 'info'

[package]
oci_concurrency = 6

[package.deploy]
retries = 3
timeout = 900000000000

[package.deploy.set]
CLUSTER_NAME = "lab"
DOMAIN = "[DOMAIN-NAME]"
K3D_IMAGE = "rancher/k3s:v1.31.9-k3s1"
K3D_EXTRA_ARGS = "--k3s-arg --tls-san=[INTERNAL-IP]@server:*"
COREDNS_OVERRIDES = '''rewrite stop {
  name regex (.*\.admin\.[DOMAIN-NAME]) admin-ingressgateway.istio-admin-gateway.svc.cluster.local answer auto
}
rewrite stop {
  name regex (.*\.[DOMAIN-NAME]) tenant-ingressgateway.istio-tenant-gateway.svc.cluster.local answer auto
}'''
```

### Maru Task Integration
Tasks leverage the `ZARF_CONFIG` environment variable for declarative deployment:

```yaml
tasks:
  - name: deploy-k3d-lab
    description: "Deploy using lab configuration"
    actions:
      - description: "Deploy with lab config"
        cmd: |
          uds zarf package deploy "$PACKAGE_FILE" --confirm
        # Uses default zarf-config.toml

  - name: deploy-k3d-staging
    description: "Deploy using staging configuration"
    actions:
      - cmd: |
          uds zarf package deploy "$PACKAGE_FILE" --confirm
        env:
          - ZARF_CONFIG=configs/zarf-config-staging.toml
```

## Deployment Workflows

### Architecture-Aware Package Handling
```bash
# Auto-detect architecture (default)
uds run pull-k3d-package

# Cross-platform testing (AMD64 on ARM64 host)
uds run pull-k3d-package --set ARCHITECTURE=amd64
```

### Environment-Specific Deployment
```bash
# Lab environment (default config)
uds run k3d-lab-setup

# Staging environment
uds run deploy-k3d-staging

# Production-like configuration
uds run deploy-k3d-production
```

### Manual Deployment Testing
```bash
# Using default config
uds zarf package deploy [PACKAGE-FILE] --confirm

# Using specific config
export ZARF_CONFIG=configs/zarf-config-staging.toml
uds zarf package deploy [PACKAGE-FILE] --confirm
```

## Limitations and Constraints

### Configuration Scope Boundaries
Zarf config files can only override **explicitly exposed package variables**. Component-specific settings not exposed as package variables cannot be modified through configuration files.

**Successful Override Example:**
- `COREDNS_OVERRIDES` - Exposed as chart variable in `uds-dev-stack` component

**Cannot Override:**
- Minio chart values in `values/minio-values.yaml`
- MetalLB configuration not exposed as variables
- Hardcoded component settings

### TOML Syntax Requirements
Multi-line strings containing regex patterns require literal string syntax:
```toml
# Correct - literal strings preserve backslashes
COREDNS_OVERRIDES = '''rewrite stop { name regex (.*\.domain) ... }'''

# Incorrect - basic strings interpret backslashes as escape sequences
COREDNS_OVERRIDES = """rewrite stop { name regex (.*\.domain) ... }"""
```

## Comparison with UDS Bundle Approach

UDS bundles provide greater configuration flexibility through:

1. **Dynamic Variable Injection**: Bundle-level variables map to package variables at deployment
2. **Chart Value Override Mechanisms**: Additional tooling beyond Zarf's native variable system
3. **Template Processing**: Bundle orchestration layer modifies package behavior dynamically

The direct Zarf package approach trades some flexibility for simplicity and reduced toolchain dependencies.

## Infrastructure Requirements

- **K3d**: Version 5.7.1 or higher
- **Container Runtime**: Docker with adequate file descriptor limits
- **Network**: Host networking for port mapping (development environments)
- **Architecture**: ARM64 or AMD64 (cross-architecture testing supported)

## File Descriptor Configuration
The `K3D_ULIMIT_NOFILE` setting addresses Kubernetes file descriptor requirements:
- Default system limits (1024-4096) insufficient for cluster operations
- Setting `1048576:1048576` (1M soft:hard) prevents "too many open files" errors
- Applied to K3d containers running K3s processes

## Key Insights

1. **Package vs Component Variables**: Only package-level variables defined in `zarf.yaml` can be overridden via config files
2. **Chart Variable Exposure**: Components must explicitly expose chart values as variables for external configuration
3. **Architecture Handling**: Zarf automatically handles architecture-specific package selection unless overridden
4. **Configuration Precedence**: Command-line `--set` flags override config file values
5. **Environment Isolation**: Multiple config files enable consistent environment-specific deployments

## Recommendations

For similar deployments:
1. Evaluate upstream package variable exposure before committing to config-file approach
2. Consider forking upstream packages when extensive customization is required
3. Use UDS bundles when complex component-level overrides are necessary
4. Maintain separate config files for each target environment
5. Test architecture-specific deployments when supporting multiple platforms