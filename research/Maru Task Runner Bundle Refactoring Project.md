---
tags: [maru, uds-cli, task-runner, kubernetes, deployment, automation, bundles, zarf, aws-secrets-manager, ci-cd, devops]
---

# Maru Task Runner Bundle Refactoring Project

## Executive Summary

Refactored a UDS bundle deployment system using Maru task runner to eliminate code duplication, implement DRY principles, and support air-gapped deployment workflows. Reduced task definitions from ~30+ repetitive tasks to 12 parameterized tasks while adding AWS Secrets Manager integration and automated artifact management.

## Project Context

**Tool:** Maru task runner (integrated in UDS CLI as `uds run`)
**Purpose:** Automate UDS bundle creation and deployment for Kubernetes environments
**Architecture:** Multi-environment (dev/test/prod) bundle system with air-gap transfer support

### Bundle Structure

```bash
bundles/
├── high/              # Production-grade bundle
│   ├── dev/
│   ├── test/
│   └── prod/
└── low/               # Development bundle (includes additional tooling)
    ├── dev/
    ├── test/
    └── prod/
```

## Key Accomplishments

### 1. Task Consolidation & DRY Implementation

**Before:**

- Separate tasks for each environment (dev-create, test-create, prod-create)
- ~30+ tasks with duplicated logic
- Hard to maintain and extend

**After:**

- 3 generic parameterized tasks (create, deploy, deploy-packages)
- 12 total tasks including convenience shortcuts
- Single source of truth for logic

### 2. Parameterized Task Design

Created reusable generic tasks with inputs:

```yaml
- name: create
  inputs:
    environment: [dev, test, prod]
    bundle: [high, low]
    secret_name: AWS Secrets Manager secret
  actions:
    - Conditionally fetch AWS secret
    - Conditionally run low-bundle-specific tasks
    - Create bundle with proper architecture
```

**Key Features:**

- Input validation with defaults
- Conditional execution using `if` statements
- Environment variable propagation for shell commands
- Architecture specification (amd64) for consistent cross-platform builds

### 3. AWS Secrets Manager Integration

Implemented secure configuration management:

```yaml
- name: fetch-aws-secret
  description: Fetch UDS config from AWS Secrets Manager
  inputs:
    bundle: Bundle name
    environment: Target environment
    secret_name: Secret identifier
    region: AWS region (default: us-gov-east-1)
  actions:
    - Fetch secret and write to proper config path
```

**Benefits:**

- No credentials in version control
- Environment-specific configurations
- Works in both external and air-gapped environments

### 4. Air-Gap Transfer Workflow

Built complete air-gap deployment pipeline:

**External Side (with internet):**

```bash
# 1. Create bundle
uds run bundles:dev-create

# 2. Package entire repo for transfer
uds run bundles:package-for-transfer \
  --set-input bundle=low \
  --set-input environment=dev \
  --set-input version=v1.0.0

# Uploads to: s3://[S3-BUCKET-NAME]/bundles/
```

**Internal Side (air-gapped bastion):**

```bash
# 1. Download from S3
aws s3 cp s3://[S3-BUCKET-NAME]/bundles/bundle-[PROJECT]-low-dev-v1.0.0.tar.gz .

# 2. Extract
tar -xzf bundle-[PROJECT]-low-dev-v1.0.0.tar.gz

# 3. Deploy
cd [PROJECT-DIR]
uds run bundles:dev-deploy
```

### 5. Flexible Deployment Options

Unified deployment task supporting both full and selective deployments:

```yaml
- name: deploy
  inputs:
    packages: Optional comma-separated package list (empty = all)
  actions:
    - Conditionally add -p flag only when packages specified
```

**Usage:**

```bash
# Deploy everything
uds run bundles:dev-deploy

# Deploy specific packages
uds run bundles:dev-deploy --set-input packages="gitlab,gitlab-runner"
```

### 6. Artifact Cleanup Automation

Created comprehensive cleanup task:

```yaml
- name: clean
  description: Remove all build artifacts
  actions:
    - List artifacts to be deleted
    - Confirm deletion (skippable with --set-input confirm=true)
    - Remove transfer tarballs
    - Remove bundle artifacts (*.tar.zst)
    - Remove Zarf packages
    - Remove fetched configs
```

## Technical Solutions

### Challenge 1: Variable Substitution in Shell Commands

**Problem:** Maru template variables (`${{ .inputs.var }}`) not processed when mixed with shell variables (`${VAR}`)

**Solution:** Use environment variables in action `env` block:

```yaml
env:
  - BUNDLE_PATH=bundles/${{ .inputs.bundle }}/${{ .inputs.environment }}
  - UDS_ARCH=amd64
cmd: ./uds deploy "${BUNDLE_PATH}/uds-bundle-${BUNDLE_NAME}-${UDS_ARCH}.tar.zst"
```

### Challenge 2: Conditional Task Execution

**Problem:** Different bundles require different preparatory steps (e.g., TLS secret copy only for low bundle)

**Solution:** Used Maru's `if` conditionals:

```yaml
- task: packages:copy-gateway-tls-secret
  if: ${{ eq .inputs.bundle "low" }}
```

### Challenge 3: Architecture Specification

**Problem:** macOS M3 (arm64) conflicting with amd64-only container images

**Solution:** Hardcoded `UDS_ARCH=amd64` in environment variables and passed to UDS CLI

### Challenge 4: Optional Package Deployment

**Problem:** Needed single task for both full deployments and selective package upgrades

**Solution:** Conditional flag addition in shell:

```yaml
cmd: |
  DEPLOY_CMD="./uds deploy ${BUNDLE_PATH}/uds-bundle.tar.zst --confirm"
  if [ -n "${PACKAGES}" ]; then
    DEPLOY_CMD="${DEPLOY_CMD} -p ${PACKAGES}"
  fi
  eval ${DEPLOY_CMD}
```

### Challenge 5: Cross-Platform Tarball Creation

**Problem:** BSD tar (macOS) doesn't support `--transform` flag

**Solution:** Use parent directory approach:

```yaml
cmd: |
  cd ..
  tar -czf "${REPO_NAME}/${TARBALL_NAME}" \
    --exclude="${REPO_NAME}/.git" \
    "${REPO_NAME}"
  cd "${REPO_NAME}"
```

## File Structure

### Root tasks.yaml

```yaml
includes:
  - bundles: ./tasks/bundles.yaml

tasks:
  - name: dev
    description: Build and create the dev bundle
    actions:
      - task: bundles:dev-create
```

### tasks/bundles.yaml

Contains all bundle-related tasks:

- Generic tasks: `create`, `deploy`, `deploy-packages`
- Helper tasks: `fetch-aws-secret`, `package-for-transfer`, `clean`
- Convenience shortcuts: `dev-create`, `dev-deploy`, `test-create`, etc.

## IAM Permissions Required

For bastion host role to access AWS Secrets Manager:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:[PARTITION]:secretsmanager:[REGION]:[ACCOUNT-ID]:secret:uds-config*"
    }
  ]
}
```

## Best Practices Implemented

1. **Atomic Tasks:** Small, focused, reusable task definitions
2. **Descriptive Naming:** Hierarchical naming (e.g., `bundles:dev-create`)
3. **Parameter Validation:** Required/optional inputs with sensible defaults
4. **Error Prevention:** File existence checks and conditional execution
5. **Security:** No hardcoded credentials, AWS Secrets Manager integration
6. **Documentation:** Clear descriptions for all tasks and inputs
7. **Maintainability:** Single source of truth for deployment logic

## Usage Examples

### Complete Workflow: External to Air-Gap Deployment

```bash
# External environment
uds run bundles:dev-create
uds run bundles:package-for-transfer \
  --set-input bundle=low \
  --set-input environment=dev \
  --set-input version=v1.2.3

# Transfer happens via S3

# Air-gapped bastion
aws s3 cp s3://[S3-BUCKET-NAME]/bundles/bundle-[PROJECT]-low-dev-v1.2.3.tar.gz .
tar -xzf bundle-[PROJECT]-low-dev-v1.2.3.tar.gz
cd [PROJECT-DIR]
uds run bundles:dev-deploy

# Upgrade specific package later
uds run bundles:dev-deploy --set-input packages="gitlab"
```

### Cleanup After Build

```bash
# Interactive
uds run bundles:clean

# Automated
uds run bundles:clean --set-input confirm=true
```

## Lessons Learned

1. **Variable Scoping:** Maru template variables must be resolved before shell execution - use `env` blocks
2. **Conditional Logic:** Maru's `if` expressions enable powerful task composition without duplication
3. **Cross-Platform Compatibility:** Test tar operations on both macOS and Linux
4. **Air-Gap Patterns:** "Push entire repo" approach simpler than registry-based transfers for smaller projects
5. **Input Design:** Optional inputs with empty defaults provide maximum flexibility

## Future Enhancements

- [ ] Add versioning automation (timestamp-based versions)
- [ ] Implement checksum verification for transferred artifacts
- [ ] Add deployment rollback capability
- [ ] Create task for diff comparison between environments
- [ ] Add metrics collection for deployment duration
- [ ] Implement pre-deployment validation checks

## References

- [Maru Task Runner Documentation](https://github.com/defenseunicorns/maru-runner)
- [UDS CLI Documentation](https://github.com/defenseunicorns/uds-cli)
- [Zarf Package Manager](https://zarf.dev)

## Tags Reference

Primary technologies: `maru`, `uds-cli`, `zarf`, `kubernetes`
Operations: `deployment`, `automation`, `ci-cd`, `air-gap`
Infrastructure: `aws-secrets-manager`, `s3`, `bundles`
Categories: `task-runner`, `devops`, `configuration-management`
