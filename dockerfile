# Dockerfile
FROM chainguard/wolfi-base:latest@sha256:918a593b8268c222afd4e2c4f06860ac984e60719b4697e4c71d796bc8fcd042

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