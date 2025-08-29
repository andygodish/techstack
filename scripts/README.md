
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
- **Conflict resolution**: Automatically handles multiple files with same names (e.g., `overview.md`)
- **Portable**: Runs in Docker container - use anywhere without installing dependencies
- **Flat output**: Creates unique filenames perfect for NotebookLM batch uploads
- **Flexible**: Recursive/non-recursive search, custom prefixes, verbose logging

## Usage Examples

```bash
# Basic collection - all .md files
docs -s ./docs

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
# See what docs changed
git diff --name-only HEAD origin/main | grep '\.md$'

# Collect only if changes exist
if [[ -n $(git diff --name-only HEAD origin/main | grep '\.md$') ]]; then
    docs -s ./docs --overwrite
fi
```

**Multi-repository collection:**
```bash
# Collect from multiple repos into shared directory
cd ~/projects/app1 && docs -s ./docs -p "app1" -o /tmp/all-docs
cd ~/projects/app2 && docs -s ./guides -p "app2" -o /tmp/all-docs
# Upload everything from /tmp/all-docs to NotebookLM
```

## Development Notes

Built iteratively to solve real documentation collection challenges:

1. **Started** with simple bash script for local file copying
2. **Added** conflict resolution for multiple `overview.md` files
3. **Containerized** with Docker for cross-repository portability
4. **Debugged** bash compatibility issues between local and container environments
5. **Optimized** for clean CLI experience without wrapper scripts

Key technical decisions:
- Flat file naming (not directory structure) for NotebookLM compatibility
- `set -e` with safe arithmetic operations for reliable error handling
- Security-focused base image with SHA pinning
- Volume mounting current directory as `/workspace` for seamless operation