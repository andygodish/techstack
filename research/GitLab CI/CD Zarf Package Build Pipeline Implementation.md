---
tags: [gitlab, zarf, ci-cd, kubernetes, s3, artifact-storage, security-scanning, trivy, maru, helm, eks, aws-govcloud, troubleshooting, docker, build-pipeline]
---

# GitLab CI/CD Zarf Package Build Pipeline Implementation

## Overview

Implemented a complete GitLab CI/CD pipeline for building Zarf packages with integrated artifact storage and security scanning capabilities in a Kubernetes environment.

## Infrastructure Analysis

### GitLab Configuration
- Kubernetes deployment using Helm charts on EKS
- S3 backend storage for all GitLab components including artifacts
- IRSA authentication with service account: `arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]`
- Artifact storage bucket: `[S3-BUCKET-NAME]` in `[AWS-REGION]`

### Storage Architecture
- GitLab uses hashed storage pattern for artifacts: `[project-hash]/[date]/[pipeline-id]/[job-id]/`
- Content-addressable storage in `@final/` directories for deduplication
- Metadata stored separately from artifact content

## Pipeline Development

### Initial Setup
- Started with basic artifact upload job using fake content
- Encountered payload size limits (413 error) with 4.7GB Zarf package
- Resolved by increasing GitLab artifact size limit to 5GB

### Build Process Implementation
```yaml
build-zarf-package:
  stage: build
  image: [REGISTRY-URL]/defenseunicorns/toolbox:0.1.0
  services:
    - name: [REGISTRY-URL]/library/docker:dind
      alias: docker
  variables:
    DOCKER_HOST: tcp://docker:2376
    DOCKER_TLS_CERTDIR: "/certs"
```

### Key Components
- Docker-in-Docker setup for container image processing
- Registry authentication using `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD`
- Maru task runner integration: `uds run create-dev-package`

## Zarf Package Analysis

### Package Structure
- Base metadata: jam-guts package version 0.0.1
- Container images: 6 images totaling approximately 4.7GB
- Architecture: layered Zarf configuration with flavor support
- Output: `zarf-package-jam-guts-amd64-0.0.1.tar.zst`

### Build Tool Stack
- UDS CLI v0.27.7 with integrated Zarf v0.56.0
- Maru task runner for orchestration
- Toolbox container with comprehensive scanning tools

## Security Scanning Integration

### Trivy Vulnerability Scanning
- Successfully scanned Python-based container image (Debian 13.0)
- Found 30+ CVEs across system packages and Python dependencies
- Critical findings: setuptools vulnerabilities allowing RCE and path traversal
- Tool availability: Trivy v0.63.0, Grype v0.94.0 in toolbox image

### Scanning Categories Identified
1. **Vulnerability Scanning**: Trivy for CVE detection
2. **Compliance Checking**: check-for-root user validation  
3. **Malware Detection**: ClamAV (not available in current toolbox)

## Artifact Verification

### S3 Storage Confirmation
- Artifacts successfully stored in hashed directory structure
- Verified artifact integrity through metadata inspection
- Content stored as ZIP archives with proper compression
- File path: `[project-hash]/@final/[content-hash]`

### Database Query Results
- Confirmed all artifacts stored with `file_store = '2'` (object storage)
- No local filesystem storage (`file_store = '1'`) detected

## Technical Challenges Resolved

1. **Docker Connectivity**: Implemented DinD service for container operations
2. **Registry Authentication**: Configured automatic GitLab registry login
3. **Resource Limits**: Increased artifact size limits for large Zarf packages
4. **Storage Backend**: Verified S3 integration through configuration analysis

## Next Steps

- Implement security scan pipeline stages with appropriate failure thresholds
- Add check-for-root compliance validation
- Create component-based task system for reusable CI/CD patterns
- Establish artifact retention policies based on branch/tag patterns

## Configuration References

### Helm Values Structure
```yaml
global:
  minio:
    enabled: false
  appConfig:
    object_store:
      enabled: true
      connection:
        provider: AWS
        region: [AWS-REGION]
    artifacts:
      bucket: [S3-BUCKET-NAME]
```

### Pipeline Requirements
- Toolbox image with UDS CLI, Zarf, Trivy, and Docker CLI
- IRSA-based S3 authentication
- Docker-in-Docker capability for image processing
- Maru task runner for build orchestration

## Lessons Learned

- GitLab's hashed storage system provides efficient deduplication but requires understanding the file organization pattern
- Large artifact handling requires careful consideration of storage limits and transfer times
- Security scanning integration works best when tools are pre-installed in standardized container images
- IRSA authentication eliminates the need for hardcoded credentials in CI/CD pipelines
- Maru task runner provides effective abstraction for complex build processes