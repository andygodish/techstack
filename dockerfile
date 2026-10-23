# Dockerfile
FROM chainguard/wolfi-base:latest@sha256:d69a74aa929a006d05880a9287fbbf89aa278d55d7239955331f239122824ba6

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