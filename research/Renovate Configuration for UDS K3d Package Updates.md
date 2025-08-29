---
tags: [renovate, uds-k3d, automation, dependency-management, kubernetes, github-releases, yaml, configuration]
---

# Renovate Configuration for UDS K3d Package Updates

## Overview

This document outlines the Renovate configuration implemented to automatically update the UDS K3d package version in YAML task files. The configuration monitors GitHub releases and creates pull requests when new versions are available.

## Configuration Details

### Custom Manager Setup

The Renovate configuration uses a regex-based custom manager to detect and update version strings in YAML files:

- **File Pattern**: Matches `.yml` and `.yaml` files
- **Target Variable**: `K3D_PACKAGE_VERSION` 
- **Data Source**: GitHub releases from `defenseunicorns/uds-k3d`
- **Versioning**: Semantic versioning (semver)

### Regex Pattern

The configuration targets this specific YAML structure:
```yaml
- name: K3D_PACKAGE_VERSION
  description: "Version of the UDS K3d package"
  default: "0.15.0"
```

### Package Rules

- **Grouping**: Updates are grouped under "UDS K3d Package"
- **Commit Format**: Uses semantic commit messages with `deps(k3d)` scope
- **Topic**: "UDS K3d package" for clear identification

## Implementation

### Setup Steps

1. Place the `renovate.json` configuration file in repository root
2. Enable Renovate on the repository (GitHub App or self-hosted)
3. Renovate will automatically scan for updates on schedule

### Expected Behavior

- **Detection**: Automatically finds K3D_PACKAGE_VERSION variables in YAML files
- **Monitoring**: Checks GitHub releases for new UDS K3d versions
- **Updates**: Creates PRs with version bumps when new releases are available
- **Commit Messages**: Follows format: `deps(k3d): update UDS K3d package to v[VERSION]`

This worked out of the box on this repo.

## Configuration File Structure

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:base"],
  "customManagers": [
    {
      "customType": "regex",
      "fileMatch": ["\\.ya?ml$"],
      "matchStrings": ["..."],
      "datasourceTemplate": "github-releases",
      "depNameTemplate": "defenseunicorns/uds-k3d",
      "versioningTemplate": "semver"
    }
  ],
  "packageRules": ["..."]
}
```

## Benefits

- **Automation**: Eliminates manual version checking and updating
- **Security**: Ensures timely updates for security patches
- **Consistency**: Standardized commit messages and PR format
- **Reliability**: Uses semantic versioning for proper version comparison

## Troubleshooting

### Common Issues

- **No Updates Detected**: Verify regex pattern matches your YAML structure exactly
- **Wrong Repository**: Confirm `depNameTemplate` points to correct GitHub repository
- **Version Format**: Ensure target repository uses semantic versioning tags

### Validation

Test the regex pattern against your YAML files to ensure proper matching before deployment.

## Maintenance

- **Schema Updates**: Keep Renovate schema reference current
- **Pattern Updates**: Modify regex if YAML structure changes
- **Repository Changes**: Update `depNameTemplate` if source repository changes

## Related Documentation

- [Renovate Custom Managers](https://docs.renovatebot.com/modules/manager/custom/)
- [GitHub Releases Datasource](https://docs.renovatebot.com/modules/datasource/github-releases/)
- [UDS K3d Repository](https://github.com/defenseunicorns/uds-k3d)