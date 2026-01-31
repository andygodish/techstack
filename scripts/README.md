# `docs` - Documentation Collection Tool

A portable CLI tool for collecting documentation files from any repository and preparing them for NotebookLM uploads.

## Quick Start

```bash
# Build the Docker image (one-time setup)
docker build -t docs .

# Use in any repository
docker run --rm -v "$(pwd):/workspace" docs -s ./documentation

# Optional: Create an alias for easier usage
alias docs='docker run --rm -v "$(pwd):/workspace" docs'
```

## Features

- **Multi-format support**: Collect `.md`, `.mdx`, `.txt`, `.rst`, and other documentation formats
- **MDX conversion**: Automatically converts `.mdx` files to `.md` extension while preserving all content
- **Conflict resolution**: Automatically handles multiple files with same names (e.g., `overview.md`)
- **Portable**: Runs in Docker container - use anywhere without installing dependencies
- **Flat output**: Creates unique filenames perfect for NotebookLM batch uploads
- **Flexible**: Recursive/non-recursive search, custom prefixes, verbose logging

## Usage Examples

## `research-bundle` - Build a NotebookLM bundle from `./research`

This helper selects recent research docs (by keyword hits + recency) and copies the best matches into a flat folder for drag/drop into NotebookLM.

Examples:

```bash
# Top 25 matches from last year
./scripts/research-bundle --query "kubernetes irsa" --days 365 --limit 25

# Last 14 days, no query (recency-only)
./scripts/research-bundle --days 14 --limit 200

# Use a regex query
./scripts/research-bundle --query "\\birsa\\b|\\boidc\\b" --regex --days 365 --limit 50
```

Output is written under `./notebook-bundles/<timestamp>__<slug>/`:
- `index.md` (human index)
- `manifest.json`
- flattened copies of selected docs


```bash
# Basic collection - all .md files
docs -s ./docs

# Collect .mdx files (automatically converts to .md extension)
docs -s ./src/content/docs -e "mdx" -p "zarf"

# Multiple file types with custom prefix
docs -s ./documentation -e "md,mdx" -p "my-project"

# Non-recursive search with verbose output
docs -s ./guides -e "txt,rst,md" -R -v

# Custom output directory
docs -s ./api-docs -o ./upload-ready

# Overwrite existing files
docs -s ./docs --overwrite
```

## Command Options

```
REQUIRED:
    -s, --source DIR        Source directory to collect files from

OPTIONS:
    -o, --output DIR        Output directory (default: ./notebook-upload)
    -e, --extensions EXT    Comma-separated file extensions (default: md)
    -p, --prefix NAME       Prefix for renamed files (default: directory name)
    -r, --recursive         Search recursively (default: true)
    -R, --no-recursive      Disable recursive search
    --overwrite             Overwrite existing files in output directory
    -v, --verbose           Verbose output
    -h, --help              Show help
```

## File Naming Convention

Files are renamed to avoid conflicts:
- `./docs/overview.md` → `docs-overview.md`
- `./api/guides/setup.md` → `api-guides-setup.md`
- `./research/analysis.md` → `research-analysis.md`

**MDX Conversion:**
- `./src/content/docs/getting-started/index.mdx` → `docs-getting-started-index.md`
- All JSX components and imports are preserved - the LLM understands them as context

## Docker Setup

The tool uses a secure Chainguard Wolfi base image:

```dockerfile
FROM chainguard/wolfi-base:latest@sha256:b72df108f3388c82b0638bcfbad1511d85c60593e67fb8f8a968255f7e0588df
RUN apk add --no-cache bash findutils coreutils
COPY scripts/docs /usr/local/bin/docs
WORKDIR /workspace
ENTRYPOINT ["docs"]
```

## Troubleshooting

**Build fails with layer cache error:**
```bash
docker system prune -f
docker build --no-cache -t docs .
```

**Permission issues with output files:**
```bash
sudo chown -R $(id -u):$(id -g) ./notebook-upload/
```

**Want to see what files will be collected:**
```bash
# Dry run with verbose output
docs -s ./docs -v
```

## Workflow Integration

**With Git change detection:**
```bash
# See what docs changed (both .md and .mdx)
git diff --name-only HEAD origin/main | grep -E '\.(md|mdx)$'

# Collect only if changes exist
if [[ -n $(git diff --name-only HEAD origin/main | grep -E '\.(md|mdx)$') ]]; then
    docs -s ./docs -e "md,mdx" --overwrite
fi
```

**Multi-repository collection:**
```bash
# Collect from multiple repos into shared directory
cd ~/projects/app1 && docs -s ./docs -p "app1" -o /tmp/all-docs
cd ~/projects/zarf && docs -s ./src/content/docs -e "mdx" -p "zarf" -o /tmp/all-docs
# Upload everything from /tmp/all-docs to NotebookLM
```

**Common use cases:**
```bash
# Standard markdown documentation
docs -s ./docs

# Astro/Next.js MDX documentation  
docs -s ./src/content/docs -e "mdx"

# Mixed documentation formats
docs -s ./documentation -e "md,mdx,txt,rst"

# Large documentation sites with custom prefix
docs -s ./site/src/content/docs -e "mdx" -p "project-name" -v
```

## Development Notes

Built iteratively to solve real documentation collection challenges:

1. **Started** with simple bash script for local file copying
2. **Added** conflict resolution for multiple `overview.md` files
3. **Containerized** with Docker for cross-repository portability
4. **Debugged** bash compatibility issues between local and container environments
5. **Added** MDX support for modern documentation sites (Astro, Next.js, etc.)
6. **Optimized** for clean CLI experience without wrapper scripts

Key technical decisions:
- Flat file naming (not directory structure) for NotebookLM compatibility
- Simple MDX conversion: change extension only, preserve all content
- `set -e` with safe arithmetic operations for reliable error handling
- Security-focused base image with SHA pinning
- Volume mounting current directory as `/workspace` for seamless operation