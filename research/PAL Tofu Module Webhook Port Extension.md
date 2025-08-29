---
tags: [terraform, tofu, hcl, JG, aws, nlb, load-balancer, webhook, networking, troubleshooting, infrastructure, port-forwarding, uds-core]
---

# PAL Module Webhook Port Extension - Implementation Guide

## Overview

This document covers the modification of the Public Access Layer (PAL) Terraform module to support additional webhook ports (25001-25012) alongside existing HTTP/HTTPS traffic (ports 80/443). The modification involved refactoring from static resource definitions to dynamic generation using Terraform's `for` expressions.

The forking adds in a merging of an additional set of ports that are merged alongside 80/443.

## Architecture Context

The PAL module creates a Network Load Balancer (NLB) in a public VPC that forwards traffic to Istio tenant gateway load balancers in a private VPC via Transit Gateway. The NLB targets three reserved IP addresses (one per AZ) that correspond to the Istio tenant gateway service.

### Traffic Flow
```
Internet → NLB (Public VPC) → Transit Gateway → Istio Tenant Gateway NLB (Private VPC) → K8s Services
```

## Implementation Approach

### Original Static Configuration
The original module used hardcoded resource definitions:
- Security group rules for ports 80/443
- Target groups named `tenant_target_group_http/https`
- Listeners for HTTP/HTTPS
- Manual target group attachments

### Modified Dynamic Configuration
The refactored approach uses Terraform locals with `for` expressions to generate:
- Security group rules for all ports dynamically
- Target groups with consistent naming (`tenant_target_group_${port}`)
- Listeners for all required ports
- Target group attachments across all three AZs

## Code Changes

### Variables Addition
Added webhook port support to the module's variable structure:
```hcl
variable "public_access_layer_options" {
  type = object({
    cidr          = optional(string, "192.168.0.0/22")
    webhook_ports = optional(list(number), [])
  })
  default = {}
}
```

### Locals Refactoring
Created comprehensive locals to dynamically generate all required resources:
```hcl
locals {
  web_ports = [80, 443]
  webhook_ports = var.public_access_layer_options.webhook_ports
  all_ports = concat(local.web_ports, local.webhook_ports)
  
  # Dynamic security group rules, listeners, target groups, and attachments
  # Using merge() and for expressions for all configurations
}
```

### Key Implementation Details
- Used `merge()` to combine web and webhook port configurations
- Implemented consistent naming patterns: `tenant_target_group_${port}`
- Generated target group attachments for all three AZs per port
- Maintained backward compatibility with existing port configurations

## Module Usage

### Calling the Modified Module
```hcl
module "public_access_layer" {
  source = "git::https://[DOMAIN]/[ORG]/terraform-aws-uds-modified-gateway-pal.git?ref=main"
  
  deployment_requirements = module.mission_init.deployment_requirements
  public_access_layer_requirements = {
    azs                    = module.mission_init.azs
    private_vpc_properties = module.private_vpc.vpc_properties
  }
  public_access_layer_options = {
    webhook_ports = [25001, 25002, 25003, 25004, 25005, 25006, 25007, 25008, 25009, 25010, 25011, 25012]
  }
}
```

## Encountered Issues and Solutions

### Issue 1: Module Source Caching
**Problem**: Terraform cached the old module version despite remote repository updates.

**Error**: 
```
Error: Duplicate variable declaration
Variable names must be unique within a module.
```

**Solution**: Force fresh module download using query parameter:
```hcl
source = "git::https://[DOMAIN]/[ORG]/terraform-aws-uds-modified-gateway-pal.git?ref=main"
```

**Alternative**: Clear module cache with `rm -rf .terraform/modules/`

### Issue 2: Target Group Naming Conflicts
**Problem**: Dynamic resource generation created naming conflicts with existing target groups.

**Error**:
```
Error: ELBv2 Target Group (tenant-gateway-[TENANT]-80) already exists
Error: ELBv2 Target Group (tenant-gateway-[TENANT]-443) already exists
```

**Root Cause**: Terraform attempted to create new target groups with identical names to existing ones, but couldn't replace them due to active listener dependencies.

### Issue 3: Resource Dependencies and Deletion Order
**Problem**: Target groups couldn't be deleted while still referenced by active listeners.

**Error**:
```
Error: deleting ELBv2 Target Group: ResourceInUse: Target group is currently in use by a listener or a rule
```

**Root Cause**: AWS prevents deletion of target groups that are actively referenced by load balancer listeners, creating a circular dependency during the refactoring process.

### Issue 4: Import vs. Recreation Complexity
**Problem**: Importing existing target groups into new resource addresses created complex state conflicts.

**Attempted Solution**: 
```bash
tofu import 'module.public_access_layer.module.tenant_gateway_nlb.aws_lb_target_group.this["tenant_target_group_80"]' [TARGET-GROUP-ARN]
```

**Result**: Import succeeded but created additional dependency conflicts during apply phase.

## Final Resolution Strategy

### Manual Dependency Cleanup
The most effective solution involved manually breaking the dependency chain:

1. **Delete Load Balancer Listeners**
   - Navigate to EC2 → Load Balancers → [NLB-NAME]
   - Delete listeners for ports 80 and 443
   - **Note**: This causes immediate traffic interruption

2. **Delete Target Groups**
   - Navigate to EC2 → Target Groups  
   - Delete `tenant-gateway-[TENANT]-80` and `tenant-gateway-[TENANT]-443`

3. **Apply Terraform Configuration**
   ```bash
   tofu apply -target=module.public_access_layer
   ```

### Downtime Considerations
- Manual listener deletion causes immediate HTTP/HTTPS traffic interruption
- Total downtime: ~2-3 minutes during Terraform apply process
- Webhook ports (25001-25012) created successfully without conflicts

## Results

### Successfully Created Resources
- **Security Group Rules**: 14 total (2 web + 12 webhook ports)
- **Target Groups**: 14 total with consistent naming pattern
- **Listeners**: 14 TCP listeners on the NLB
- **Target Group Attachments**: 42 total (14 ports × 3 AZs)

### Resource Naming Pattern
- Target Groups: `tenant-gateway-[TENANT]-[PORT]`
- Security Rules: `web_[PORT]` and `webhook_[PORT]`
- Listeners: `HTTP`/`HTTPS` for web, `webhook_[PORT]` for webhooks

## Lessons Learned

### Terraform Module Vendoring
- Vendored modules provide air-gapped deployment capability
- Module caching can be persistent; use version tags or cache clearing
- Local modifications require careful source management

### Load Balancer Resource Dependencies
- Target groups cannot be deleted while referenced by listeners
- Resource replacement order is critical in load balancer configurations
- Manual intervention may be required for complex refactoring scenarios

### Dynamic Resource Generation Benefits
- Significantly reduces code duplication
- Improves maintainability for port range modifications  
- Enables consistent naming and configuration patterns
- Scales easily for future port additions

### State Management Complexity
- Importing resources can create complex state scenarios
- Sometimes manual cleanup is simpler than state manipulation
- Resource dependencies require careful planning during refactoring

## Future Improvements

### Enhanced Error Handling
- Add validation for port ranges to prevent conflicts
- Implement resource lifecycle rules for safer updates
- Consider blue-green deployment strategies for zero-downtime updates

### Module Flexibility
- Add support for custom target group health checks
- Enable port-specific security group rule customization
- Implement conditional resource creation based on feature flags

### Monitoring and Validation
- Add outputs for webhook port endpoints
- Include health check status monitoring
- Implement automated validation of port connectivity

## Conclusion

The PAL module modification successfully extended webhook support from 2 ports to 14 ports while maintaining existing functionality. The dynamic resource generation approach provides a scalable foundation for future port additions. While the implementation encountered several Terraform state and dependency challenges, the manual resolution approach provided a reliable path to completion with minimal downtime.

The refactored module now supports both web traffic (80/443) and webhook traffic (25001-25012) through a single, maintainable configuration that can be easily extended for additional ports as needed.