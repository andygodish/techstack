---
tags: [ssl-certificates, lets-encrypt, certbot, dns-route53, aws-govcloud, platform-deployment, domain-configuration, base64-encoding, kubernetes-secrets]
---

# SSL Certificate Generation and Platform Deployment Guide

## Overview

This guide documents the process of generating wildcard SSL certificates using Let's Encrypt and deploying them to a platform that requires base64-encoded certificate data. The process involves DNS-01 challenge validation through AWS Route 53 in a GovCloud environment.

## Prerequisites

- Domain registered with AWS Route 53 (commercial or GovCloud)
- AWS CLI configured with appropriate Route 53 permissions
- Platform requiring SSL certificates with domain variable and base64-encoded cert/key data

## Domain and Certificate Requirements

### Target Domains
- Primary domain: `[DOMAIN-NAME].net`
- Environment subdomains:
  - `dev.[DOMAIN-NAME].net`
  - `test.[DOMAIN-NAME].net` 
  - `prod.[DOMAIN-NAME].net`

### Certificate Coverage
Each environment requires wildcard certificates covering:
- `*.[ENVIRONMENT].[DOMAIN-NAME].net`
- `*.admin.[ENVIRONMENT].[DOMAIN-NAME].net`

## Installation and Setup

### Installing Certbot with Route 53 Plugin

On macOS with Homebrew-managed Python:

```bash
# Install pipx for isolated application management
brew install pipx

# Install certbot as isolated application
pipx install certbot

# Add Route 53 plugin to certbot's environment
pipx inject certbot certbot-dns-route53
```

This approach avoids Python environment conflicts by creating an isolated environment for certbot.

## DNS Configuration Challenge

### Initial Issue: Cross-Environment DNS
The initial setup revealed a common issue where:
- Domain was registered in AWS commercial account
- New hosted zone created in AWS GovCloud
- DNS queries were reaching wrong environment

### Symptoms
```bash
dig [SUBDOMAIN].[DOMAIN-NAME].net +short
# Returned no results despite Route 53 records existing
```

### Resolution
Domain nameservers needed updating from commercial Route 53 nameservers to GovCloud nameservers:

**Commercial nameservers (old):**
- `ns-1886.awsdns-43.co.uk`
- `ns-9.awsdns-01.com`
- `ns-861.awsdns-43.net`
- `ns-1061.awsdns-04.org`

**GovCloud nameservers (new):**
- `ns-1493.awsdns-us-gov-58.com`
- `ns-1685.awsdns-us-gov-18.net`
- `ns-339.awsdns-us-gov-42.org`
- `ns-592.awsdns-us-gov-10.us`

## Certificate Generation Process

### DNS-01 Challenge Flow
1. Certbot contacts Let's Encrypt requesting certificates
2. Let's Encrypt provides unique challenge tokens
3. Certbot creates temporary TXT records in Route 53:
   - `_acme-challenge.[SUBDOMAIN].[DOMAIN-NAME].net`
4. Let's Encrypt verifies records via public DNS
5. Certificates issued upon successful validation
6. Temporary DNS records automatically cleaned up

### Certificate Generation Commands

```bash
# Primary domain
certbot certonly --dns-route53 \
  -d "*.[DOMAIN-NAME].net" \
  -d "*.admin.[DOMAIN-NAME].net" \
  --email [EMAIL-ADDRESS] \
  --agree-tos \
  --non-interactive \
  --config-dir ~/certs/config \
  --work-dir ~/certs/work \
  --logs-dir ~/certs/logs

# Development environment
certbot certonly --dns-route53 \
  -d "*.dev.[DOMAIN-NAME].net" \
  -d "*.admin.dev.[DOMAIN-NAME].net" \
  --email [EMAIL-ADDRESS] \
  --agree-tos \
  --non-interactive \
  --config-dir ~/certs/config \
  --work-dir ~/certs/work \
  --logs-dir ~/certs/logs

# Repeat for test and prod environments
```

### Certificate Storage Location
Certificates stored in:
```
~/certs/config/live/[DOMAIN]/
├── fullchain.pem    # Certificate chain
├── privkey.pem      # Private key
├── cert.pem         # Certificate only
└── chain.pem        # Intermediate certificates
```

## Base64 Encoding for Platform Deployment

### macOS Base64 Syntax
macOS `base64` command uses different syntax than Linux:

```bash
# Encode certificate to base64
base64 -i ~/certs/config/live/[DOMAIN]/fullchain.pem -o cert.b64

# Encode private key to base64  
base64 -i ~/certs/config/live/[DOMAIN]/privkey.pem -o key.b64
```

### Common Pitfall
Avoid overwriting source files:
```bash
# WRONG - overwrites original file
base64 -w0 key.pem > key.pem

# CORRECT - creates new output file
base64 -i key.pem -o key.b64
```

## AWS Credential Access

### How Certbot Accesses AWS
Certbot uses boto3 library following AWS credential provider chain:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. AWS config file (`~/.aws/config`)
4. IAM role (if on EC2)
5. AWS CLI configured profiles

### Verification
```bash
# Check current AWS identity
aws sts get-caller-identity

# Test Route 53 access
aws route53 list-hosted-zones
```

## DNS Propagation and Testing

### Verification Steps
```bash
# Check nameserver delegation
dig [DOMAIN-NAME].net NS +short

# Test direct nameserver query
dig @ns-1493.awsdns-us-gov-58.com [SUBDOMAIN].[DOMAIN-NAME].net +short

# Test public DNS propagation
dig @8.8.8.8 [SUBDOMAIN].[DOMAIN-NAME].net +short
```

### Propagation Timing
- Direct nameserver queries: Immediate
- Public DNS propagation: 2-48 hours
- Local DNS cache: May require manual flushing

## Platform Integration

### Load Balancer Setup
Platform uses Network Load Balancer (NLB) with multiple availability zones:
- NLB provides multiple public IP addresses
- Traffic routes to Istio tenant gateway
- Istio directs traffic via virtual services based on host headers

### DNS Records for Services
Create A records pointing to NLB IPs:
```bash
aws route53 change-resource-record-sets --hosted-zone-id [ZONE-ID] --change-batch '{
  "Changes": [{
    "Action": "CREATE",
    "ResourceRecordSet": {
      "Name": "[SERVICE].[DOMAIN-NAME].net",
      "Type": "A",
      "TTL": 300,
      "ResourceRecords": [
        {"Value": "[IP-1]"},
        {"Value": "[IP-2]"},
        {"Value": "[IP-3]"}
      ]
    }
  }]
}'
```

## File Distribution

### S3 Bucket Transfer
```bash
# Upload directory to S3
aws s3 cp [LOCAL-DIRECTORY] s3://[S3-BUCKET-NAME]/ --recursive

# Download from S3 to remote system
aws s3 cp s3://[S3-BUCKET-NAME]/ [LOCAL-DIRECTORY] --recursive
```

## Troubleshooting

### Common Issues

**Certificate Generation Failures:**
- Verify AWS credentials and Route 53 permissions
- Check domain nameserver delegation
- Ensure DNS propagation completed

**Platform Deployment Errors:**
- Verify base64 encoding format
- Check file permissions (group readable: `chmod g+r filename`)
- Validate certificate covers required domains

**Registry Push Failures:**
- Check in-cluster registry logs: `kubectl logs -n [NAMESPACE] [REGISTRY-POD]`
- Verify S3 backend connectivity and permissions
- Consider registry pod restart: `kubectl delete pod [REGISTRY-POD]`

### DNS Propagation Issues
If DNS queries fail but direct nameserver queries work:
- Wait for propagation (up to 48 hours)
- Clear local DNS cache
- Test from different locations/networks
- Use online DNS propagation checkers

## Security Considerations

### Credential Management
- Never embed AWS credentials in containers
- Use IAM roles for service accounts (IRSA) in production
- Rotate certificates before expiration (90 days for Let's Encrypt)

### File Handling
- Protect private key files with appropriate permissions
- Use secure methods for transferring certificate data
- Clean up temporary files containing sensitive data

## Certificate Lifecycle

### Renewal Process
Let's Encrypt certificates expire after 90 days. Renewal requires:
1. Re-running certbot commands before expiration
2. Updating platform configuration with new base64 values
3. Testing certificate deployment

### Monitoring
- Set calendar reminders for certificate expiration
- Consider automated renewal scripts for production environments
- Monitor certificate expiration dates in platform dashboards