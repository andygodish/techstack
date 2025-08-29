---
tags: [bash, cli-tools, docker, documentation, automation, file-collection, development, troubleshooting, portable-tools, workflow]
---

# Docs Collection Tool - Development

## Problem Statement

Managing documentation across multiple repositories for NotebookLM uploads presented several challenges:

- **Multiple `overview.md` files** across different repos causing naming conflicts
- **Mixed file formats** (`.md`, `.mdx`) requiring transformation
- **Manual file collection** being time-intensive and error-prone  
- **Directory structures** needing to be flattened for NotebookLM uploads
- **Cross-repository usage** without copying scripts around

## Solution Architecture

### Core Requirements
- **Dynamic file extension support** for various documentation formats
- **Conflict resolution** through intelligent file naming
- **Portable execution** via Docker containers
- **Flat output structure** suitable for NotebookLM batch uploads
- **Flexible source targeting** with customizable prefixes

### Technology Stack
- **Shell**: Bash for cross-platform compatibility and file system operations
- **Containerization**: Docker with Chainguard Wolfi base for security
- **File Processing**: Native Unix tools (`find`, `cp`, `sed`)

## Development Process

### Phase 1: Local Script Development

Started with a bash script in the techstack repository to handle basic file collection:

```bash
# Initial concept
./scripts/file-collector.sh -s ./research
```

**Key Features Implemented:**
- Command-line argument parsing with `getopt` patterns
- File extension filtering with comma-separated support
- Recursive vs non-recursive directory traversal
- Verbose logging with color-coded output
- File existence checking with overwrite protection

**Critical Design Decisions:**
- Used `#!/usr/bin/env bash` for better portability
- Implemented consistent placeholder patterns for security
- Added YAML front matter requirements for documentation tagging

### Phase 2: Naming Strategy Development

**Challenge**: Multiple repositories containing files with identical names (e.g., `overview.md`)

**Solution**: Developed a naming convention using source directory and file path:
```
[PREFIX]-[SANITIZED-PATH]-[FILENAME]
```

**Examples:**
- `./docs/api/overview.md` → `myapp-api-overview.md`
- `./research/analysis.md` → `research-analysis.md`

**File Sanitization Rules:**
- Replace `/` with `-` in paths
- Convert special characters to `_`
- Preserve original file extensions

### Phase 3: Docker Containerization

**Motivation**: Enable usage across different repositories without script duplication

**Container Strategy:**
```dockerfile
FROM chainguard/wolfi-base:latest@sha256:[HASH]
RUN apk add --no-cache bash findutils coreutils
COPY scripts/docs /usr/local/bin/docs
WORKDIR /workspace
ENTRYPOINT ["docs"]
```

**Key Design Choices:**
- **Security-focused base image**: Chainguard Wolfi for minimal attack surface
- **Volume mounting**: Current directory as `/workspace` for seamless file access
- **Pinned base image**: SHA-based pinning for reproducible builds
- **Clean entrypoint**: Direct script execution without wrapper complexity

### Phase 4: Cross-Platform Compatibility Issues

**Problem Encountered**: Script worked locally but failed in Docker environment

**Symptoms:**
- Local execution: Processed all 10 files correctly
- Docker execution: Only processed 1 file then stopped

**Root Cause Analysis:**
```bash
# Debug commands used
docker run --rm -v "$(pwd):/workspace" --entrypoint bash docs -c "find ./research -type f -name '*.md'"
docker run --rm -v "$(pwd):/workspace" docs -s ./research --overwrite -v
```

**Issue Identified**: The `set -e` directive combined with arithmetic operations
```bash
# Problematic code
((counter++))  # Returns exit code 1 when counter is 0

# Fixed version  
counter=$((counter + 1))  # Always returns exit code 0
```

**Resolution**: Modified counter increment patterns to be compatible with `set -e`

### Phase 5: User Experience Optimization

**Simplification**: Removed wrapper script complexity in favor of direct Docker usage
```bash
# Final clean usage pattern
docker build -t docs .
docker run --rm -v "$(pwd):/workspace" docs -s ./source-dir

# Optional alias for convenience
alias docs='docker run --rm -v "$(pwd):/workspace" docs'
```

**File Naming Decision**: Tested directory structure vs flat naming
- **Tested**: `research/filename.md` (creates subdirectories)
- **Chosen**: `research-filename.md` (flat structure)
- **Rationale**: NotebookLM uploads work better with flat file structures

## Technical Implementation Details

### File Discovery Algorithm
```bash
find_files() {
    local source_dir="$1"
    local extensions="$2" 
    local recursive="$3"
    
    IFS=',' read -ra ext_array <<< "$extensions"
    
    for ext in "${ext_array[@]}"; do
        ext=$(echo "$ext" | xargs)
        if [[ "$recursive" == true ]]; then
            find "$source_dir" -type f -name "*.$ext" 2>/dev/null
        else
            find "$source_dir" -maxdepth 1 -type f -name "*.$ext" 2>/dev/null
        fi
    done | sort -u
}
```

### Filename Generation Logic
```bash
generate_filename() {
    local source_file="$1"
    local source_dir="$2" 
    local prefix="$3"
    
    local relative_path=$(get_relative_path "$source_file" "$source_dir")
    local filename=$(basename "$relative_path")
    local dir_path=$(dirname "$relative_path")
    
    if [[ "$dir_path" == "." ]]; then
        echo "${prefix}-${filename}"
    else
        local sanitized_dir=$(sanitize_filename "$dir_path")
        echo "${prefix}-${sanitized_dir}-${filename}"
    fi
}
```

### Error Handling Strategy
- **Fail-fast approach**: `set -e` for immediate error detection
- **Graceful degradation**: Continue processing remaining files on individual failures
- **Verbose logging**: Color-coded output for debugging and monitoring
- **Exit status handling**: Proper error codes for CI/CD integration

## Security Considerations

### Container Security
- **Minimal base image**: Chainguard Wolfi reduces attack surface
- **No privilege escalation**: Runs as non-root user
- **Ephemeral containers**: `--rm` flag ensures cleanup
- **SHA pinning**: Prevents supply chain attacks

### Data Sanitization
Following established AI Security Guidelines:
- **No credential exposure** in output files
- **Placeholder patterns** for sensitive information
- **Generic naming conventions** avoiding [ORGANIZATION] specifics

## Usage Patterns

### Single Repository Collection
```bash
# In any repository
docs -s ./documentation
docs -s ./docs -e "md,mdx" -p "project-name"
```

### Multi-Repository Workflow
```bash
# Collect from multiple repos into shared directory
cd ~/projects/app1
docs -s ./docs -p "app1" -o /tmp/all-docs

cd ~/projects/app2
docs -s ./guides -p "app2" -o /tmp/all-docs

# Upload everything from /tmp/all-docs to NotebookLM
```

### Development Workflow Integration
```bash
# Check for git changes first
git diff --name-only HEAD origin/main | grep '\.md$'

# Collect only changed documentation
docs -s ./docs -v --overwrite
```

## Lessons Learned

### Bash Scripting Best Practices
- **Arithmetic safety**: Use `$((expression))` instead of `((expression))` with `set -e`
- **Array handling**: Different bash versions handle arrays differently across environments
- **Error propagation**: Explicit error checking for critical operations
- **Cross-platform compatibility**: Test in multiple environments early

### Docker Development Workflow
- **Layer caching**: Structure Dockerfile to maximize cache hits
- **Debug accessibility**: Provide `--entrypoint bash` override for troubleshooting
- **Volume permissions**: Consider user ID mapping for file ownership
- **Base image security**: Prefer security-focused distributions

### CLI Tool Design
- **Single responsibility**: Keep each tool focused on one task
- **Composability**: Design for integration with other tools
- **Predictable output**: Consistent file naming and directory structures
- **Graceful failure**: Continue processing when individual operations fail

## Future Enhancement Opportunities

### Planned Features
- **Multi-source support**: Process multiple directories in single invocation
- **MDX transformation**: Built-in conversion from MDX to Markdown
- **Tag-based filtering**: Select files based on YAML front matter tags
- **Git integration**: Automatic detection of changed files

### Potential Improvements
- **Progress indicators**: Show processing status for large file collections
- **Parallel processing**: Concurrent file operations for performance
- **Configuration files**: Support for project-specific settings
- **Template generation**: Automatic YAML front matter addition

## Conclusion

The docs collection tool evolved from a simple file copying script to a robust, containerized solution addressing real workflow challenges. Key success factors included:

- **Iterative development** with immediate user feedback
- **Docker containerization** for portability and consistency  
- **Security-first approach** with minimal, pinned base images
- **Practical problem-solving** over theoretical perfection

The tool now enables efficient documentation collection across multiple repositories while maintaining security standards and providing a foundation for future automation enhancements.