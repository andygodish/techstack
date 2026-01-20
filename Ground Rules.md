# AI Security Guidelines for Documentation Generation

I save research documents that summarize my tech-related work to a remote repo. Provide a separate markdown file for easy copy and paste into a research directory outlining what was discussed in this AI chat.

## CRITICAL: Data Sanitization Rules

**These rules MUST be followed when generating any documentation, summaries, or reports.**

### AWS & Cloud Provider Information

- ❌ **NEVER include IAM Role ARNs** - replace with `arn:aws:iam::[ACCOUNT-ID]:role/[ROLE-NAME]`
- ❌ **NEVER include S3 bucket names** that contain account identifiers or environment specifics
- ❌ **NEVER include Access Keys, Secret Keys, or any credential values**
- ❌ **NEVER include VPC IDs, Subnet IDs, or Security Group IDs**
- ✅ **DO use placeholders**: `[AWS-ACCOUNT-ID]`, `[S3-BUCKET-NAME]`, `[IAM-ROLE-ARN]`

### Network & Infrastructure

- ❌ **NEVER include internal IP addresses** (10.x.x.x, 172.16-31.x.x, 192.168.x.x ranges)
- ❌ **NEVER include specific domain names** or hostnames of internal services
- ❌ **NEVER include cluster names** that reveal organization structure
- ✅ **DO use placeholders**: `[INTERNAL-IP]`, `[CLUSTER-NAME]`, `[DOMAIN-NAME]`
- ✅ **DO use generic terms that would be publicly found in documentation**: `s3.us-gov-east-1.amazonaws.com`, `uds-gov-east1`

### Organization Information

- ❌ **NEVER include company names, project codenames, or internal identifiers**
- ❌ **NEVER include specific environment names** that reveal infrastructure details
- ❌ **NEVER include database connection strings** or service URLs
- ✅ **DO use generic terms**: `[COMPANY]`, `[PROJECT]`, `[ENVIRONMENT]`

### Kubernetes & Container Information

- ❌ **NEVER include specific namespace names** that reveal environment structure
- ❌ **NEVER include container registry URLs** with organization details
- ❌ **NEVER include specific ConfigMap or Secret names** with environment identifiers
- ✅ **DO use placeholders**: `[NAMESPACE]`, `[REGISTRY-URL]`, `[CONFIG-NAME]`

### Security & Monitoring

- ❌ **NEVER include API keys, tokens, or certificates**
- ❌ **NEVER include monitoring dashboard URLs** or alert manager configurations
- ❌ **NEVER include specific log aggregation endpoints**
- ✅ **DO describe functionality without exposing endpoints**

### Code Repository & Version Control

- ❌ **NEVER include internal git repository URLs** that reveal organization structure
- ❌ **NEVER include specific commit hashes** from private repositories
- ❌ **NEVER include branch names** that reveal project codenames or strategies
- ✅ **DO use placeholders**: `[REPO-URL]`, `[COMMIT-HASH]`, `[BRANCH-NAME]`
- ✅ **DO use generic examples**: `https://github.com/example/repo.git`

### API & Application Details

- ❌ **NEVER include specific API endpoint paths** that reveal business logic or internal services
- ❌ **NEVER include custom header names** used for internal authentication
- ❌ **NEVER include webhook URLs** or callback endpoints
- ✅ **DO use placeholders**: `[API-ENDPOINT]`, `[WEBHOOK-URL]`
- ✅ **DO use generic patterns**: `/api/v1/resource`, `/internal/service`

## Sanitization Examples

### ❌ WRONG

```yaml
connection:
  connection_string: postgresql://secretuser:secretpassword@yourmom.com:5432/secretdatabase?sslmode=require
```

Service account: `arn:aws-us-gov:iam::123456789012:role/uds-s3irsa-dev-abc-gitlab-s3-role`

Repository: `https://gitlab.internal.company.com/secret-project/infrastructure.git`

API endpoint: `https://api.company.com/internal/v2/customer-analytics`

### ✅ CORRECT

```yaml
connection:
  provider: AWS
  region: "us-gov-east-1"
  host: "s3.us-gov-east-1.amazonaws.com"
  aws_iam_endpoint: "https://iam.us-gov.amazonaws.com"
  connection_string: postgresql://[USERNAME]:[PASSWORD]@[DB-HOST]:5432/[DATABASE-NAME]?sslmode=require
```

Service account: `arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]`

Repository: `https://[REPO-URL]/[PROJECT]/[REPO-NAME].git`

API endpoint: `https://[API-DOMAIN]/[API-ENDPOINT]`

## Replacement Patterns

When sanitizing, use these consistent placeholder patterns:

| Sensitive Data Type | Placeholder Pattern |

|-------------------|-------------------|
| AWS Account ID | `[ACCOUNT-ID]` |
| S3 Bucket Name | `[S3-BUCKET-NAME]` |
| IAM Role ARN | `arn:aws:[PARTITION]:iam::[ACCOUNT-ID]:role/[ROLE-NAME]` |
| Internal IP | `[INTERNAL-IP]` or `10.x.x.x` |
| Cluster Name | `[CLUSTER-NAME]` |
| Namespace | `[NAMESPACE]` |
| Domain Name | `[DOMAIN-NAME]` or `example.com` |
| Registry URL | `[REGISTRY-URL]` |
| [AWS Region Partition](https://docs.aws.amazon.com/whitepapers/latest/aws-fault-isolation-boundaries/partitions.html) | `[PARTITION]` |
| Git Repository URL | `[REPO-URL]` |
| Commit Hash | `[COMMIT-HASH]` |
| API Endpoint | `[API-ENDPOINT]` |
| Webhook URL | `[WEBHOOK-URL]` |

## Document Tagging Requirements

### YAML Front Matter

**ALL generated documentation MUST include YAML front matter with appropriate tags.**

Add this at the very beginning of every markdown document:

```yaml
---
tags: [tag1, tag2, tag3, tag4, tag5]
---
```

### Tagging Guidelines

**Required Tag Categories:**

1. **Primary Service/Application** - Main technology being documented
   - Examples: `gitlab`, `kubernetes`, `prometheus`, `vault`, `jenkins`

2. **Supporting Technologies** - Key infrastructure components
   - Examples: `s3`, `irsa`, `eks`, `helm`, `docker`, `terraform`

3. **Problem/Issue Type** - What kind of problem or documentation
   - Examples: `500-error`, `authentication`, `troubleshooting`, `configuration`, `deployment`

4. **Infrastructure/Platform** - Environment details
   - Examples: `aws`, `aws-govcloud`, `gcp`, `azure`, `kubernetes`, `linux`

**Tag Format Rules:**

- Use lowercase only
- Use hyphens for multi-word tags: `aws-govcloud`, `500-error`, `object-storage`
- Keep tags concise but descriptive
- Aim for 5-10 tags per document
- Include both specific and general tags for discoverability

**Example Tag Sets:**

For incident resolution:

```yaml
tags: [gitlab, irsa, s3, eks, aws-govcloud, 500-error, authentication, troubleshooting, helm, kubernetes]
```

For configuration guides:

```yaml
tags: [kubernetes, security, rbac, configuration, best-practices, kubectl]
```

For monitoring setup:

```yaml
tags: [prometheus, grafana, monitoring, alerting, kubernetes, deployment]
```

## Validation Checklist

Before generating any documentation, verify:

- [ ] No 12-digit AWS account numbers present
- [ ] No specific ARN values with real account IDs
- [ ] No internal IP addresses exposed
- [ ] No organization-specific names or identifiers
- [ ] No credential values or keys present
- [ ] All sensitive values replaced with consistent placeholders
- [ ] No internal git repository URLs or commit hashes
- [ ] No specific API endpoints that reveal business logic

### Tag Validation

Before finalizing any document, ensure:

- [ ] YAML front matter is present at the top
- [ ] At least 5 relevant tags are included
- [ ] Tags cover: service, technology, problem-type, platform
- [ ] All tags use proper lowercase and hyphen formatting
- [ ] Tags are specific enough for targeted searches

## Emergency Override

If specific values MUST be included for troubleshooting:

1. Clearly mark the section as `[INTERNAL USE ONLY - REQUIRES SANITIZATION]`
2. Add a warning comment about manual sanitization needed before commit
3. Create a separate branch for internal documentation that will NOT be pushed to remote
4. Use git pre-commit hooks to scan for common sensitive patterns
5. Never include in any exported or shared documentation
6. Document the sanitization process needed in a checklist within the section

**Recommended pre-commit hook pattern:**

```bash
# Add to .git/hooks/pre-commit
if git diff --cached | grep -E '\[INTERNAL USE ONLY'; then
  echo "ERROR: Document contains [INTERNAL USE ONLY] sections"
  echo "Please sanitize before committing"
  exit 1
fi
```

## Adding New Rules

To add new sanitization rules:

1. Identify the sensitive data pattern
2. Define the placeholder format
3. Add to the appropriate category above
4. Include examples of wrong vs. correct usage
5. Update the validation checklist
6. Update the Replacement Patterns table
