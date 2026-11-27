# Dockerfile
FROM chainguard/wolfi-base:latest@sha256:4cf5932a0f95a88af352f77e4efa67480cab0e1f7a48f0eddca3cce003a7c0fb

# Install bash and findutils using apk (Alpine-based)
RUN apk add --no-cache \
    bash \
    findutils \
    coreutils

# Create a directory for our script
RUN mkdir -p /usr/local/bin

# Copy the docs script and make it executable
COPY scripts/docs /usr/local/bin/docs
RUN chmod +x /usr/local/bin/docs

# Set the working directory to /workspace where we'll mount volumes
WORKDIR /workspace

# Set bash as the default shell
SHELL ["/bin/bash", "-c"]

# Default entrypoint runs the docs command
ENTRYPOINT ["docs"]