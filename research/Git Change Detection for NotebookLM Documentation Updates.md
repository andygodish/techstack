---
tags: [git, documentation, notebooklm, version-control, automation, markdown, workflow, change-detection, ci-cd, development-tools]
---

# Git Change Detection for NotebookLM Documentation Updates

## Overview

When maintaining documentation in NotebookLM that's synchronized with a Git repository, it's essential to identify which markdown files have changed before pulling updates. This prevents unnecessary re-uploads and ensures you only update the files that actually need attention in your NotebookLM notebook.

## Problem Statement

- Documentation stored in Git repository with `.md` files
- NotebookLM notebook contains uploaded versions of these documents
- Need to identify changed files before `git pull` to minimize re-upload work
- Want to avoid checking every file manually after updates

## Solution Approaches

### Method 1: Check Remote Changes Before Pulling

The most effective approach is to fetch remote changes without merging and compare with your current state:

```bash
# Fetch remote changes without merging
git fetch origin

# Show only changed markdown files
git diff --name-only HEAD origin/main | grep '\.md$'

# Show detailed changes in markdown files
git diff HEAD origin/main -- '*.md'
```

**Benefits:**
- Shows exactly what will change before pulling
- Allows selective review of modifications
- No merge conflicts to resolve first

### Method 2: Check Local Uncommitted Changes

Before pulling, also verify you don't have local modifications that might conflict:

```bash
# Check for modified .md files in working directory
git status --porcelain | grep '\.md$'

# Show actual changes in local markdown files
git diff --name-only -- '*.md'
```

### Method 3: Automated Workflow Script

Create a reusable script for consistent checking:

```bash
#!/bin/bash
# File: check-md-changes.sh

echo "Checking for markdown file changes..."
git fetch origin

CHANGED_MD=$(git diff --name-only HEAD origin/main | grep '\.md$')

if [ -n "$CHANGED_MD" ]; then
    echo "The following .md files have changes:"
    echo "$CHANGED_MD"
    echo ""
    echo "Run 'git diff HEAD origin/main -- \"*.md\"' to see detailed changes"
    echo "After reviewing, run 'git pull' and re-upload these files to NotebookLM"
else
    echo "No markdown files have changed - safe to pull without NotebookLM updates"
fi
```

## Implementation Steps

### Step 1: Pre-Pull Check
```bash
# Quick one-liner to see what changed
git fetch origin && git diff --name-only HEAD origin/main | grep '\.md$'
```

### Step 2: Review Changes (Optional)
```bash
# See what actually changed in the content
git diff HEAD origin/main -- '*.md'
```

### Step 3: Pull Updates
```bash
git pull origin main
```

### Step 4: Update NotebookLM
Only re-upload the markdown files that showed changes in Step 1.

## Advanced Techniques

### Filter by Directory
If your documentation is organized in specific directories:

```bash
# Only check docs in specific folder
git diff --name-only HEAD origin/main -- 'docs/*.md'

# Check multiple documentation directories
git diff --name-only HEAD origin/main -- 'docs/*.md' 'guides/*.md'
```

### Show Change Statistics
```bash
# Show summary of changes per file
git diff --stat HEAD origin/main -- '*.md'
```

### Integration with CI/CD

For automated workflows, you can use this approach in CI pipelines:

```yaml
# Example GitHub Actions step
- name: Check for documentation changes
  run: |
    git fetch origin
    CHANGED_FILES=$(git diff --name-only HEAD origin/main | grep '\.md$')
    echo "changed-docs=$CHANGED_FILES" >> $GITHUB_OUTPUT
```

## Best Practices

### Daily Workflow
1. Run `git fetch origin` to get latest remote state
2. Check for `.md` changes using `git diff --name-only HEAD origin/main | grep '\.md$'`
3. Review specific changes if needed with `git diff HEAD origin/main -- '*.md'`
4. Pull updates with `git pull`
5. Re-upload only changed files to NotebookLM

### Alias for Convenience
Add to your `.gitconfig` or shell profile:

```bash
# Add to ~/.gitconfig
[alias]
    check-docs = "!git fetch origin && git diff --name-only HEAD origin/main | grep '\\.md$'"

# Usage
git check-docs
```

### Shell Function
Add to your `.bashrc` or `.zshrc`:

```bash
check_notebook_updates() {
    echo "Fetching latest changes..."
    git fetch origin
    
    local changed_md=$(git diff --name-only HEAD origin/main | grep '\.md$')
    
    if [ -n "$changed_md" ]; then
        echo "📝 Changed markdown files:"
        echo "$changed_md" | sed 's/^/  - /'
        echo ""
        echo "💡 After pulling, re-upload these files to NotebookLM"
    else
        echo "✅ No markdown files changed - safe to pull"
    fi
}
```

## Troubleshooting

### Common Issues

**Issue: No output from grep command**
- Cause: No markdown files changed or different file extensions used
- Solution: Check with `git diff --name-only HEAD origin/main` to see all changes

**Issue: "origin/main" doesn't exist**
- Cause: Default branch might be named differently
- Solution: Use `git branch -r` to list remote branches, then use correct name

**Issue: Changes show but files look identical**
- Cause: Whitespace or line ending differences
- Solution: Use `git diff --ignore-space-change HEAD origin/main -- '*.md'`

### Verification Commands

```bash
# Verify remote tracking
git branch -vv

# Check remote branch exists
git ls-remote origin

# Confirm fetch worked
git log --oneline HEAD..origin/main
```

## Alternative Tools

For teams preferring GUI tools:
- **GitKraken**: Visual diff comparison
- **Sourcetree**: Built-in change detection
- **VS Code**: Git integration with diff highlighting

## Security Considerations

When sharing documentation workflows:
- Avoid including repository URLs with [ORGANIZATION] names
- Use placeholder values for [PROJECT] or [ENVIRONMENT] specific paths
- Don't expose internal [DOMAIN-NAME] or server configurations in examples