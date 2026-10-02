# Dockerfile
FROM chainguard/wolfi-base:latest@sha256:9c2092b053779e14c82fb50f77b37bcc38b7d2c83972352d5813280f9d035b03

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