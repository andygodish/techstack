# Dockerfile
FROM chainguard/wolfi-base:latest@sha256:fac38d12efdb4bf43ac9e599a31db10a27ad5dd71e5f1618790962eda8d66180

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