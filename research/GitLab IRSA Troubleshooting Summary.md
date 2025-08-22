---
tags: [gitlab, irsa, s3, eks, aws-govcloud, 500-error, authentication, troubleshooting, helm, kubernetes]
---

# GitLab IRSA Troubleshooting Summary

## Overview
This document summarizes the troubleshooting process for resolving GitLab 500 errors related to AWS S3 object storage configuration using IRSA (IAM Roles for Service Accounts) in an EKS cluster.

## Initial Problem
- **Issue**: GitLab web UI returning 500 errors after helm upgrade
- **Environment**: EKS cluster in AWS GovCloud (us-gov-east-1)
- **Goal**: Configure GitLab to use S3 buckets via IRSA authentication

## Key Error Messages Identified

### Primary Error
```
ArgumentError (Missing required arguments: aws_access_key_id, aws_secret_access_key)
```

**Source**: fog-core library in carrierwave storage integration
**Location**: `fog-core (2.1.0) lib/fog/core/service.rb:244:in 'validate_options'`

### Stack Trace Analysis
The error originated from GitLab attempting to create internal user avatars and failing to authenticate to S3:
```
carrierwave (1.3.4) lib/carrierwave/storage/fog.rb:151:in 'connection'
app/uploaders/object_storage.rb:50:in 'store!'
lib/users/internal.rb:252:in 'create_unique_internal'
app/controllers/root_controller.rb:26:in 'index'
```

### Warning Messages
```
[fog][WARNING] Unable to fetch credentials: Expected(200) <=> Actual(403 Forbidden)
```

## Root Cause Analysis

### Configuration Issues Identified

1. **Missing Host Parameter**: The `gitlab-object-store` secret's connection configuration was missing the required `host` parameter for AWS S3 endpoint.

2. **GovCloud IAM Endpoint**: Missing the GovCloud-specific IAM endpoint configuration required for IRSA authentication.

## Solutions Implemented

### Added Missing Host Parameter & GovCloud IAM Endpoint

**Final Working Configuration:**
```yaml
connection:
  provider: AWS
  region: "us-gov-east-1"
  host: "s3.us-gov-east-1.amazonaws.com"
  aws_iam_endpoint: "https://iam.us-gov.amazonaws.com"
  use_iam_profile: true
  aws_signature_version: 4
  path_style: false
```

## Commands Used for Resolution

**Secret Update Command**

```bash
kubectl patch secret gitlab-object-store -n gitlab --type='json' -p='[{"op": "replace", "path": "/data/connection", "value": "'$(echo -n 'provider: AWS
region: "us-gov-east-1"
host: "s3.us-gov-east-1.amazonaws.com"
aws_iam_endpoint: "https://iam.us-gov.amazonaws.com"
use_iam_profile: true
aws_signature_version: 4
path_style: false' | base64 -w 0)'"}]'
```

**Restart GitLab pods:**
```bash
kubectl rollout restart deployment/gitlab-webservice-default -n gitlab
```

## Verification Steps

### IRSA Configuration Verified
- ✅ Service accounts properly annotated with IAM role ARN
- ✅ IAM role: `arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]`
- ✅ MinIO disabled (`global.minio.enabled: false`)
- ✅ Object store enabled (`global.appConfig.object_store.enabled: true`)

### Service Accounts with IRSA Annotation
```
gitlab-webservice    arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]
gitlab-sidekiq       arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]
gitlab-toolbox       arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]
gitlab-registry      arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]
```

## Bucket Configuration
GitLab configured to use the following S3 buckets:
- `[S3-BUCKET-PREFIX]-artifacts`
- `[S3-BUCKET-PREFIX]-backups`
- `[S3-BUCKET-PREFIX]-lfs`
- `[S3-BUCKET-PREFIX]-packages`
- `[S3-BUCKET-PREFIX]-registry`
- `[S3-BUCKET-PREFIX]-uploads`
- And others for various GitLab features

## Key Troubleshooting Insights

### Configuration Hierarchy
The issue was in the upstream GitLab Helm chart values, specifically:
- Global object store configuration was correct
- Service account annotations were properly applied
- The secret content itself was missing critical AWS endpoint information

### GovCloud Specific Requirements
AWS GovCloud environments require:
1. GovCloud-specific S3 endpoint: `s3.[AWS-REGION].amazonaws.com`
2. GovCloud-specific IAM endpoint: `https://iam.[AWS-PARTITION].amazonaws.com`

## Resolution Status
- ✅ AWS credentials error resolved
- ✅ Secret configuration updated with proper endpoints
- ✅ GitLab pods restarted successfully
- ⚠️ Final UI testing pending (last logs showed health checks passing)

## Recommendations

### For Future Deployments
1. Always include the `host` parameter in S3 connection configuration
2. For GovCloud deployments, include the `aws_iam_endpoint` parameter
3. Verify service account annotations are applied to all relevant GitLab components
4. Test S3 connectivity before deploying GitLab upgrades

### Monitoring
Monitor the following for similar issues:
- `fog` library warnings about credential fetching
- `ArgumentError` exceptions related to missing AWS parameters
- 403 Forbidden responses from AWS IAM endpoints

## Environment Details
- **Kubernetes**: EKS cluster
- **Region**: (AWS GovCloud)
- **GitLab Version**: 18.2.2
- **Storage**: External S3 buckets with IRSA authentication