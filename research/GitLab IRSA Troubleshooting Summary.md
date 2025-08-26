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

## Additional GitLab Runner IRSA Configuration Issue

Below demonstrates using a wildcard in the IAM role trust relationship for GitLab Runner service account when creating an IAM policy for IRSA:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws-us-gov:iam::123456789012:oidc-provider/oidc.eks.us-gov-east-1.amazonaws.com/id/FGPF95B670123456789B587219876543"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "oidc.eks.us-gov-east-1.amazonaws.com/id/FGPF95B670123456789B587219876543:aud": "sts.amazonaws.com"
                },
                "StringLike": {
                    "oidc.eks.us-gov-east-1.amazonaws.com/id/FGPF95B670123456789B587219876543:sub": "system:serviceaccount:gitlab:gitlab-*"
                }
            }
        }
    ]
}
```

## Additional IRSA Trust Policy Fix

### Problem After Initial S3 Configuration
Even after correctly configuring the GitLab object store secret with proper AWS endpoints, GitLab 500 errors persisted with the same S3 authentication failures:
```
ArgumentError (Missing required arguments: aws_access_key_id, aws_secret_access_key)
```

### Secret Configuration (Required First)
Before fixing the trust policy, ensure the `gitlab-object-store` secret has the proper configuration:

```bash
kubectl patch secret gitlab-object-store -n gitlab --type='json' -p='[{"op": "replace", "path": "/data/connection", "value": "'$(echo -n 'provider: AWS
region: "us-gov-east-1"
host: "s3.us-gov-east-1.amazonaws.com"
aws_iam_endpoint: "https://iam.us-gov.amazonaws.com"
use_iam_profile: true
aws_signature_version: 4
path_style: false' | base64 -w 0)'"}]'
```

**Note**: Adjust region and endpoints for standard AWS regions:
- `host: "s3.[region].amazonaws.com"`
- `aws_iam_endpoint: "https://iam.amazonaws.com"`

### Root Cause: Overly Restrictive IAM Trust Policy
The IAM role trust policy was configured to only allow a single, specific service account rather than the multiple service accounts that GitLab creates.

The s3irsa remote tofu module that I am using does not account for more than one service account to many buckets ration. It works for Loki because Loki only generates a single service account mapped to multiple s3 buckets. GitLab creates multiple service accounts.

**Problematic trust policy:**
```json
"Condition": {
    "StringEquals": {
        "oidc.eks.us-gov-east-1.amazonaws.com/id/[OIDC-ID]:aud": "sts.amazonaws.com",
        "oidc.eks.us-gov-east-1.amazonaws.com/id/[OIDC-ID]:sub": "system:serviceaccount:gitlab:gitlab"
    }
}
```

This only allowed the `gitlab` service account, but GitLab actually creates multiple service accounts like `gitlab-webservice`, `gitlab-sidekiq`, `gitlab-toolbox`, etc.

### Solution: Wildcard Trust Policy Pattern

Make sure you get the OICD-ID

**Fixed trust policy:**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws-us-gov:iam::[ACCOUNT-ID]:oidc-provider/oidc.eks.us-gov-east-1.amazonaws.com/id/[OIDC-ID]"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "oidc.eks.us-gov-east-1.amazonaws.com/id/[OIDC-ID]:aud": "sts.amazonaws.com"
                },
                "StringLike": {
                    "oidc.eks.us-gov-east-1.amazonaws.com/id/[OIDC-ID]:sub": "system:serviceaccount:gitlab:gitlab-*"
                }
            }
        }
    ]
}
```

**Key changes:**
1. Changed `StringEquals` to `StringLike` for the subject condition
2. Changed subject from `system:serviceaccount:gitlab:gitlab` to `system:serviceaccount:gitlab:gitlab-*`

### Resolution Commands

**Get correct OIDC provider ID:**
```bash
aws iam list-open-id-connect-providers
```

**Update trust policy:**
```bash
aws iam update-assume-role-policy \
    --role-name [IAM-ROLE-NAME] \
    --policy-document file://updated-trust-policy.json
```

**Restart GitLab services:**
```bash
kubectl rollout restart deployment/gitlab-webservice-default -n gitlab
kubectl rollout restart deployment/gitlab-sidekiq-all-in-1-v2 -n gitlab
```

### Verification
Check that multiple GitLab service accounts exist:
```bash
kubectl get serviceaccount -n gitlab | grep gitlab
```

The wildcard pattern `gitlab-*` must match the actual service account naming convention GitLab uses.

### Key Lesson
When configuring IRSA for applications that create multiple service accounts (like GitLab), use wildcard patterns in the IAM trust policy rather than specific service account names. The trust policy is just as important as the secret configuration for successful S3 authentication.