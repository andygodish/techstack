---
tags: [opentofu, terraform, commands, reference, eks, kubernetes, provider-management, troubleshooting, infrastructure, cheat-sheet]
---

# OpenTofu Commands Reference - EKS Upgrade Session

## Overview
This document provides a comprehensive reference of OpenTofu commands used during an EKS cluster upgrade and provider conflict resolution session.

## Core Commands Used

### Initialization and Provider Management

#### Basic Initialization
```bash
tofu init
```
- Initializes working directory
- Downloads required providers and modules
- Sets up backend configuration

#### Initialize with Backend Migration
```bash
tofu init -migrate-state
```
- Migrates existing state to new backend configuration
- Preserves infrastructure state while updating backend settings
- Prompts for confirmation during migration

#### Initialize with Provider Upgrades
```bash
tofu init -upgrade
```
- Allows selection of newer provider versions
- Updates `.terraform.lock.hcl` with new provider versions
- Resolves version constraint conflicts

#### Combined Migration and Upgrade
```bash
tofu init -upgrade -migrate-state
```
- Performs both backend migration and provider upgrades
- Used when both backend configuration and provider versions need updates

#### Reconfigure Backend
```bash
tofu init -reconfigure
```
- Ignores existing state and starts fresh with new backend
- Does not migrate existing state (use with caution)
- Useful when state migration is not desired

### Planning and Analysis

#### Generate Execution Plan
```bash
tofu plan
```
- Shows what changes will be made to infrastructure
- Identifies resource additions, modifications, and deletions
- Validates configuration syntax and dependencies

#### Save Plan to File
```bash
tofu plan -out=tfplan
```
- Saves execution plan to a file
- Ensures exact plan is applied later
- Prevents drift between plan and apply

#### Targeted Planning
```bash
tofu plan -target='module.[MODULE-NAME]'
```
- Plans changes for specific modules only
- Reduces scope of changes for safer deployments
- Example used: `tofu plan -target='module.[EKS-MODULE]'`

### Provider Diagnostics

#### View Provider Requirements
```bash
tofu providers
```
- Displays all provider requirements from configuration
- Shows version constraints for each provider
- Helps identify version conflicts
- Essential for debugging provider constraint issues

### Application and Deployment

#### Apply Saved Plan
```bash
tofu apply tfplan
```
- Applies exactly the plan saved in the file
- No additional prompts or changes
- Guarantees execution of reviewed plan

#### Targeted Apply
```bash
tofu apply -target='module.[MODULE-NAME]'
```
- Applies changes to specific modules only
- Used during troubleshooting to isolate changes
- Example: `tofu apply -target='module.[EKS-MODULE]'`

#### Interactive Apply
```bash
tofu apply
```
- Shows plan and prompts for confirmation
- Applies all pending changes
- Default behavior for most deployments

### State Management

#### Refresh State
```bash
tofu refresh
```
- Updates state file with real infrastructure
- Resolves drift between state and actual resources
- Sometimes resolves hash mismatches

### File and Cache Management

#### Clean Provider Cache and Lock File
```bash
rm .terraform.lock.hcl
rm -rf .terraform/
```
- Removes cached providers and modules
- Clears version lock constraints
- Forces fresh download of all dependencies
- Used when resolving version conflicts

## Troubleshooting Workflows

### Provider Version Conflicts
```bash
# 1. Identify conflicting constraints
tofu providers

# 2. Clean cached files
rm .terraform.lock.hcl
rm -rf .terraform/

# 3. Reinitialize with upgrades
tofu init -upgrade -migrate-state
```

### Backend Configuration Changes
```bash
# For state migration
tofu init -migrate-state

# For configuration updates without migration
tofu init -reconfigure
```

### Stuck or Failed Plans
```bash
# 1. Refresh state
tofu refresh

# 2. Try targeted operations
tofu plan -target='module.[SPECIFIC-MODULE]'
tofu apply -target='module.[SPECIFIC-MODULE]'

# 3. If still failing, clean and restart
rm .terraform.lock.hcl
rm -rf .terraform/
tofu init -upgrade
```

## Command Options and Flags

### Common Init Flags
- `-migrate-state`: Migrate existing state to new backend
- `-upgrade`: Allow provider version upgrades
- `-reconfigure`: Ignore existing state, reconfigure backend
- `-backend=false`: Skip backend initialization

### Common Plan/Apply Flags
- `-target=RESOURCE`: Focus on specific resources or modules
- `-out=FILE`: Save plan to file
- `-auto-approve`: Skip interactive approval (apply only)
- `-refresh=false`: Skip state refresh

### Common Provider Management
- `providers`: List all provider requirements
- `providers lock`: Generate or update provider lock file
- `providers schema`: Show provider schemas

## Best Practices from Session

1. **Always use `-out` flag for important plans**
   ```bash
   tofu plan -out=tfplan
   tofu apply tfplan
   ```

2. **Use targeted operations during troubleshooting**
   ```bash
   tofu apply -target='module.[CRITICAL-MODULE]'
   ```

3. **Check provider constraints before major changes**
   ```bash
   tofu providers | grep -A 5 -B 5 [PROVIDER-NAME]
   ```

4. **Clean cache when resolving version conflicts**
   ```bash
   rm .terraform.lock.hcl && rm -rf .terraform/
   tofu init -upgrade
   ```

5. **Always migrate state when changing backends**
   ```bash
   tofu init -migrate-state
   ```

## Error Resolution Patterns

### "Failed to resolve provider packages"
```bash
# Check constraints
tofu providers

# Clean and upgrade
rm .terraform.lock.hcl
rm -rf .terraform/
tofu init -upgrade -migrate-state
```

### "Provider produced inconsistent final plan"
```bash
# Try targeted apply
tofu apply -target='module.[AFFECTED-MODULE]'

# Or refresh and retry
tofu refresh
tofu apply
```

### "Backend configuration changed"
```bash
# Migrate state
tofu init -migrate-state

# Or reconfigure if migration not needed
tofu init -reconfigure
```

## Session-Specific Commands

### EKS Module Update
```bash
# Plan the module update
tofu plan -target='module.[EKS-MODULE]' -out=tfplan

# Apply only the EKS changes
tofu apply -target='module.[EKS-MODULE]'
```

### Provider Conflict Resolution
```bash
# Identify conflicts
tofu providers

# Update root provider constraints in code
# Then clean and reinitialize
rm .terraform.lock.hcl
rm -rf .terraform/
tofu init -upgrade -migrate-state
```

## Command Safety Levels

### Safe (Read-only)
- `tofu plan`
- `tofu providers`
- `tofu refresh` (updates state, but no infrastructure changes)

### Moderate Risk
- `tofu init` (changes local files)
- `tofu apply -target=` (limited scope changes)

### High Risk
- `tofu apply` (full infrastructure changes)
- `tofu init -reconfigure` (can lose state reference)
- `rm .terraform/` (loses cached data)

## Notes

- All commands shown use `tofu` (OpenTofu), but are equivalent to `terraform` commands
- Always review plans carefully before applying
- Use version control for all configuration changes
- Test in non-production environments first
- Keep backup of state files when possible