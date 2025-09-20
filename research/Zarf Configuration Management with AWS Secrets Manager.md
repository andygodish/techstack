---
tags: [zarf, aws-secrets-manager, maru, configuration-management, multi-account, cross-account-roles, ci-cd, gitlab, toml, automation]
---

# Zarf Configuration Management with AWS Secrets Manager

## Overview

This document outlines the implementation of dynamic Zarf configuration management using AWS Secrets Manager and Maru task runner for multi-environment deployments across separate AWS accounts.

## Problem Statement

The challenge involved managing environment-specific `zarf-config.toml` files for a multi-account deployment pipeline where:
- Three environments exist: dev, test, prod (each in separate AWS accounts)
- GitLab CI/CD runs from the dev environment
- Zarf package creation requires environment-specific configuration
- Configuration contains sensitive values that shouldn't be hardcoded in repositories

## Technical Requirements

### Zarf Configuration Behavior
- Zarf automatically looks for `zarf-config.toml` in the current working directory when executing `zarf package create`
- Configuration files contain sensitive deployment parameters that vary by environment
- Files must be present at build time but shouldn't be stored in version control

### Multi-Account Architecture
- **Dev Account**: Contains GitLab instance and CI/CD runners
- **Test Account**: Target deployment environment
- **Prod Account**: Target production environment
- Single pipeline must deploy to all three accounts from dev environment

## Solution Architecture

### Configuration Storage Strategy
Store TOML configuration files as plaintext secrets in AWS Secrets Manager:
- Secret naming pattern: `zarf-config/[ENVIRONMENT]` (e.g., `zarf-config/dev`, `zarf-config/prod`)
- Store complete TOML file content as secret string value
- Leverage existing IRSA authentication from GitLab runner setup

### Cross-Account Access Pattern
Implement AWS recommended cross-account role assumption pattern:
- **Source**: GitLab runner in dev account with existing IRSA role
- **Target**: Create deployment roles in test and prod accounts
- **Trust Relationship**: Target account roles trust dev account's GitLab role
- **Workflow**: Runner assumes target account role, retrieves environment-specific secret

### Maru Task Implementation
Created automated task for configuration retrieval:

```yaml
- name: fetch-zarf-config
  description: "Retrieve Zarf configuration from AWS Secrets Manager"
  inputs:
    SECRET_NAME:
      description: "Name of the AWS secret containing the Zarf config"
      default: "zarf-config/dev"
    AWS_REGION:
      description: "AWS region where the secret is stored"
      default: "us-gov-east-1"
  actions:
    - cmd: |
        echo "Fetching Zarf config from secret: ${{ .inputs.SECRET_NAME }} in region: ${{ .inputs.AWS_REGION }}"
      
        aws secretsmanager get-secret-value \
          --secret-id "${{ .inputs.SECRET_NAME }}" \
          --region "${{ .inputs.AWS_REGION }}" \
          --query SecretString \
          --output text > zarf-config.toml
        
        if [ ! -s "zarf-config.toml" ]; then
          echo "Error: Failed to retrieve configuration or file is empty"
          exit 1
        fi
        
        echo "Successfully retrieved zarf-config.toml"
      description: "Download Zarf config from AWS Secrets Manager"
```

## Implementation Details

### Zarf Schema Limitations
During development, discovered that Zarf's schema has different variable capabilities:
- **Package-level variables**: Support `sensitive: true` property to hide values in logs
- **Chart-level variables**: Do not support `sensitive` property - only have `name`, `description`, and `path` properties

### Usage Patterns
The task integrates with existing workflows:

```bash
# Use defaults (dev environment)
uds run fetch-zarf-config

# Override for specific environment
uds run fetch-zarf-config --set SECRET_NAME=zarf-config/prod --set AWS_REGION=us-gov-west-1

# Chain with package creation
uds run fetch-zarf-config --set SECRET_NAME=zarf-config/test
uds run create-package
```

### Security Considerations
- Configuration files exist temporarily during build process only
- No sensitive values stored in version control or task definitions
- Cross-account access uses AWS native IAM role assumption
- Each environment's secrets remain isolated in respective accounts
- Audit trail maintained through CloudTrail for all secret access

## Multi-Account Deployment Strategy

### Role Architecture
- **Dev Account**: GitLab runner with existing IRSA role
- **Test Account**: Deployment role with trust relationship to dev account GitLab role
- **Prod Account**: Deployment role with trust relationship to dev account GitLab role

### Access Flow
1. GitLab runner starts with dev account IRSA credentials
2. For test deployment: `aws sts assume-role --role-arn arn:aws:iam::[TEST-ACCOUNT-ID]:role/deployment-role`
3. Use temporary credentials for test account operations including secret retrieval
4. For prod deployment: assume prod account role similarly
5. Each account's secrets remain isolated and accessible only through proper role assumption

## Integration with Existing Infrastructure

### GitLab CI/CD Pipeline
- Leverages existing toolbox image with UDS CLI, Zarf, AWS CLI
- Uses established IRSA authentication pattern
- Integrates with existing Maru task structure and workflow patterns
- Maintains compatibility with current artifact storage and security scanning processes

### Task Organization
The configuration management task fits into the existing task hierarchy:
- Root `tasks.yaml` includes various task files for different functions
- Configuration retrieval becomes prerequisite for package creation tasks
- Maintains separation of concerns with dedicated configuration management functionality

## Best Practices Applied

### Security
- Principle of least privilege through scoped cross-account roles
- Temporary credential usage instead of persistent cross-account keys
- Environment isolation through separate AWS accounts and secrets
- No plaintext sensitive values in CI/CD configuration

### Operational
- Consistent naming patterns for secrets across environments
- Error handling and validation for secret retrieval
- Integration with existing tooling and workflow patterns
- Maintainable task structure with clear input parameters

### Development
- Declarative configuration through Maru tasks
- Parameterized tasks for environment flexibility
- Integration with existing UDS/Zarf toolchain
- Version control friendly approach with externalized sensitive configuration

## Future Considerations

This implementation provides foundation for:
- Additional environment expansion (staging, integration, etc.)
- Enhanced secret rotation capabilities
- Integration with infrastructure-as-code secret generation
- Centralized configuration management across multiple projects
- Enhanced audit and compliance reporting through AWS CloudTrail integration