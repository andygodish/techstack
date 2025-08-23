---
tags: [loki, uds-core, kubernetes, logging, observability, platform-engineering, grafana, vector, prometheus, service-mesh]
---

# Loki for UDS Core Platform Engineering

## Overview

Loki is a log aggregation system that serves as a core component of the UDS (Unicorn Delivery System) Core logging functional layer.

## What is Loki?

Loki is a **log aggregation system** designed to store and query logs efficiently, often called "Prometheus for logs" due to its similar approach to indexing and querying. Created by Grafana Labs, Loki is designed to be:

- **Cost-effective**: Only indexes metadata labels, not full log content
- **Scalable**: Horizontally scalable with object storage backends  
- **Cloud-native**: Built for containerized environments like Kubernetes

## Loki's Role in UDS Core Architecture

### Integration Within UDS Core Components

UDS Core provides a secure baseline platform for cloud-native systems in highly regulated environments, and Loki fits into the observability stack alongside:

- **Service mesh security** (Istio)
- **Identity/authentication** (Keycloak)
- **Policy enforcement** (UDS Policy Engine/Pepr)
- **Monitoring/observability** (Prometheus, Grafana, Loki)
- **Backup/restore capabilities** (Velero)

### Log Collection Architecture in UDS Core

The typical Loki deployment requires a **log collection agent** deployed on each node/server to gather and forward logs. Common options include:
- **Promtail**: Grafana's native agent (lightweight, Loki-specific)
- **Fluentd**: Popular CNCF project (feature-rich, high resource usage)
- **Logstash**: Elastic Stack component (powerful but heavy)
- **Vector**: Modern observability data pipeline (chosen by UDS Core)

1. **Vector as Log Collection Client**: 
   - Deployed as Kubernetes DaemonSet (one pod per node)
   - **Role**: Acts as the log collection agent that gathers logs from all containers/services on each node
   - Collects container logs, system logs, and application logs
   - Handles log parsing, filtering, and enrichment
   - Ships processed logs to Loki with appropriate metadata labels
   - **Advantage**: High performance, low resource footprint, advanced data transformation capabilities

2. **Loki Core Engine**: 
   - Receives logs from Vector agents
   - Stores log data in object storage backend
   - Uses schema-based index management for efficiency
   - Provides query interface for log retrieval

3. **Grafana Integration**:
   - Provides unified UI for logs, metrics, and traces
   - Enables correlation between Prometheus metrics and Loki logs
   - Supports alerting based on log patterns and volume

### UDS Core Security Integration

- **Service Mesh Compatibility**: Works with both Istio sidecar and ambient modes
- **Network Policies**: Log collection respects UDS Core's "deny by default" security model
- **Authentication**: Grafana access controlled through Keycloak SSO integration
- **Policy Compliance**: Vector and Loki deployments follow UDS Policy Engine requirements

## Loki vs Splunk: Platform Engineering Perspective

### Architectural Differences

| Aspect | Loki | Splunk |
|--------|------|--------|
| **Indexing Strategy** | Metadata labels only | Full-text indexing |
| **Cost Model** | Storage-based, very economical | Volume-based ingestion pricing |
| **Query Performance** | Fast for label-based, slower for content search | Fast full-text search |
| **Deployment Model** | Cloud-native, Kubernetes-focused | Traditional enterprise, cloud options available |

### Why Loki Fits UDS Core's Mission

**Cost Predictability**: Critical for platform teams delivering to multiple customers
- No surprise bills based on log volume spikes
- Predictable storage costs scale with actual usage
- Eliminates need for log sampling or retention compromises

**Operational Simplicity**: Aligns with "secure baseline" philosophy  
- Fewer infrastructure components to manage and secure
- Natural integration with existing Prometheus/Grafana stack
- Kubernetes-native deployment and scaling patterns

**Cloud-Native Architecture**: Perfect fit for containerized environments
- Horizontal scaling matches microservices growth patterns
- Object storage backend leverages existing cloud infrastructure
- Container-aware log collection with namespace isolation

## Vector Agent Configuration and Operation

### What Vector Does as a Kubernetes DaemonSet

**Primary Function**: Vector collects container logs from **all pods** on each Kubernetes node and forwards them to Loki.

**You're partially correct about `/var/log`**, but it's more specific:

### Log Collection Sources

1. **Container Logs** (Primary):
   - **Path**: `/var/log/pods/[namespace]_[pod-name]_[uid]/[container-name]/[sequence].log`
   - **Content**: All stdout/stderr from every container on the node
   - **Format**: Each line prefixed with timestamp and stream type (stdout/stderr)

2. **Host System Logs** (Secondary):
   - **Path**: `/var/log/` directory for system services like containerd, kubelet
   - **Content**: Node-level service logs, SSH auth messages, syslog entries
   - **Purpose**: Infrastructure troubleshooting and security monitoring

3. **Kubernetes Events** (Special):
   - **Source**: Kubernetes API server (stored in etcd)
   - **Content**: Pod lifecycle events, scheduling decisions, resource issues
   - **Access**: Requires API calls, not file system access

### Vector's Kubernetes-Specific Features

**Automatic Discovery**: Vector communicates with Kubernetes API to enrich log data with context

**Metadata Enrichment**: Vector automatically adds:
```yaml
# Example of enriched log entry
{
  "message": "GET /api/users 200 0.023s",           # Original log line
  "timestamp": "2024-01-15T10:30:00Z",
  "kubernetes": {
    "pod_name": "web-app-7d4b8f5c6-abc123",
    "container_name": "nginx", 
    "namespace": "production",
    "pod_labels": {"app": "web", "version": "1.2.3"},
    "container_image": "nginx:1.21",
    "node_name": "ip-10-0-1-100.ec2.internal"
  }
}
```

**Smart Filtering and Exclusions**:
- Skip logs from pods with `vector.dev/exclude: "true"` label
- Exclude specific containers: `vector.dev/exclude-containers: "container1,container2"`
- Built-in namespace exclusions for system components

### DaemonSet Deployment Pattern

**Why DaemonSet**: Ensures Vector instance runs on every node for comprehensive data collection

**Required Volume Mounts**:
```yaml
volumes:
- name: var-log
  hostPath:
    path: /var/log/                    # Container logs location
- name: var-lib-docker-containers  
  hostPath:
    path: /var/lib/docker/containers/  # Docker runtime logs (if using Docker)
- name: vector-data-dir
  hostPath: 
    path: /mnt/vector-data             # Checkpoints to avoid duplicate sends
- name: localtime
  hostPath:
    path: /etc/localtime               # Node timezone information
```

**Resource Requirements**: Vector recommends 64Mi-1024Mi memory, 500m-6000m CPU per node

### Vector Processing Pipeline

**Collection → Enrichment → Forwarding**:

1. **File Discovery**: Vector uses `kubernetes_logs` source to automatically find log files in `/var/log/pods`

2. **Log Parsing**: Handles different log formats (JSON, plain text, multiline stacktraces)

3. **Metadata Addition**: Enriches each log entry with Kubernetes context via API calls

4. **Buffering & Checkpointing**: Stores checkpoints to avoid duplicating logs during restarts

5. **Forwarding to Loki**: Batches logs and sends via HTTP POST to Loki's push API

### UDS Core Specific Considerations

**Security Integration**:
- Vector DaemonSet must have NetworkPolicy allowances for:
  - Kubernetes API server communication (metadata enrichment)
  - Loki service communication (log forwarding)
- RBAC permissions for reading pod metadata and events

**Service Mesh Compatibility**:
- Works with both Istio sidecar and ambient modes
- Vector→Loki traffic flows through service mesh
- mTLS encryption for log transmission

**Multi-tenancy Support**:
- Natural namespace-based log separation
- Label-based routing to different Loki tenants if needed
- Respects UDS Core's tenant isolation patterns

### Comparison to Other Collection Methods

**Vector DaemonSet vs Alternatives**:
- **Sidecar approach**: Vector per pod (resource intensive, not recommended)
- **Centralized approach**: Single Vector instance (doesn't scale, single point of failure)
- **Node-level DaemonSet**: ✅ **Optimal** - One agent per node, scales with cluster

### Why Vector Over Alternatives?

| Agent | Pros | Cons | UDS Core Fit |
|-------|------|------|--------------|
| **Promtail** | Native Loki integration, lightweight | Limited transformation capabilities | ❌ Lacks advanced processing UDS Core needs |
| **Fluentd** | Mature ecosystem, many plugins | Ruby-based, higher resource usage | ❌ Too resource-heavy for baseline platform |
| **Logstash** | Powerful processing, Elastic integration | JVM-based, complex configuration | ❌ Overkill and resource-intensive |
| **Vector** | Rust-based performance, advanced transforms, observability-first | Newer ecosystem | ✅ **Perfect fit**: High performance, low overhead, cloud-native |

### Vector's Role in UDS Core Architecture

**Deployment Pattern**:
```yaml
# Vector runs as DaemonSet - one pod per Kubernetes node
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: vector
  namespace: [LOGGING-NAMESPACE]
spec:
  # Ensures Vector pod on every node to collect local logs
```

**Log Flow**: `Application Containers → Vector (per-node) → Loki → Grafana`

**Key Responsibilities**:
1. **Log Discovery**: Automatically finds all container logs on the node
2. **Metadata Enrichment**: Adds Kubernetes metadata (namespace, pod, container labels)
3. **Parsing & Filtering**: Processes different log formats (JSON, plaintext, structured)
4. **Routing**: Sends logs to appropriate Loki streams based on labels
5. **Backpressure Handling**: Manages rate limiting and buffering during spikes

### Vector's Data Transmission to Loki

**What "Streaming" Means in Loki Context:**

1. **Conceptual Stream**: A sequence of log entries with identical label sets
   ```
   Stream Example: {namespace="app-prod", container="web", level="error"}
   - All logs with these exact labels belong to the same "stream"
   - Each unique label combination creates a separate stream
   ```

2. **Technical Transmission**: Vector uses **HTTP POST requests** to Loki's push API

**Transport Mechanism Details:**

**Protocol**: HTTP/HTTPS POST requests to Loki's `/loki/api/v1/push` endpoint
```http
POST /loki/api/v1/push HTTP/1.1
Host: [LOKI-SERVICE].[NAMESPACE].svc.cluster.local:3100
Content-Type: application/json
Content-Encoding: snappy

{
  "streams": [
    {
      "stream": {
        "namespace": "my-app",
        "pod": "web-pod-123",
        "container": "nginx"
      },
      "values": [
        ["1640995200000000000", "GET /api/users 200 0.023s"],
        ["1640995201000000000", "GET /api/orders 200 0.045s"]
      ]
    }
  ]
}
```

**Batching Strategy**:
- Vector **batches multiple log entries** before sending HTTP requests
- Configurable batch size and timeout (balance latency vs efficiency)
- Compression (typically Snappy) reduces network overhead
- Retry logic with backoff for failed requests

**Network Flow in UDS Core**:
```
Vector Agent (per node) 
    ↓ HTTP POST (batched)
Kubernetes Service (loki-gateway or loki-write)
    ↓ Internal routing
Loki Distributor Component
    ↓ Processing
Loki Ingester Component
    ↓ Storage
Object Storage Backend (S3/GCS)
```

## Loki's Storage Architecture: Single Store vs Legacy

## What the Hell is BoltDB?

**BoltDB** is a simple, fast, embedded key-value database written in Go. Think of it as a lightweight alternative to SQLite, but optimized for Go applications.

### BoltDB Basics

**What it is**:
- **Embedded database**: Runs inside your application, not as a separate server
- **Single file**: The entire database is just one file on disk
- **Key-value store**: Simple storage model - you store and retrieve data by keys
- **ACID transactions**: Reliable, consistent data operations
- **No dependencies**: Pure Go, no external database servers needed

**What it's NOT**:
- Not a distributed database (like Cassandra)
- Not a separate service you install (like PostgreSQL) 
- Not optimized for complex queries or relationships

### Why Loki Uses BoltDB for Indexes

**Perfect fit for Loki's index needs**:

1. **Simple Data Model**: Loki indexes are just key-value pairs:
   ```
   Key: {namespace="app", pod="web-1"} + timestamp_range
   Value: list_of_chunk_IDs_containing_those_logs
   ```

2. **Embedded Operation**: BoltDB runs inside the Loki process
   - No separate database server to manage
   - No network calls for index lookups
   - Extremely fast local file access

3. **Single File Simplicity**: Each index period becomes one BoltDB file
   ```
   /loki/index/
   ├── index_18500_ingester1.db    # One day's worth of index
   ├── index_18500_ingester2.db    # Different ingester's data
   └── index_18501_ingester1.db    # Next day
   ```

### BoltDB in Loki's "Shipper" Pattern

**The "shipper" concept**:
1. **Create locally**: Loki writes index data to local BoltDB files
2. **Ship to S3**: Periodically uploads these BoltDB files to object storage
3. **Sync from S3**: Downloads other ingesters' BoltDB files to local cache
4. **Query locally**: All index queries happen against local BoltDB files

**Why this works so well**:
- **Speed**: Local file access is much faster than network calls
- **Reliability**: BoltDB handles file locking, transactions, corruption protection
- **Simplicity**: No complex database setup or maintenance
- **Portability**: BoltDB files can be copied between systems easily

### BoltDB vs Alternatives

| Database Type | Use Case | Loki Fit |
|---------------|----------|----------|
| **BoltDB** | Embedded, single-process, simple KV | ✅ **Perfect**: Simple, fast, no ops overhead |
| **SQLite** | Embedded SQL database | ❌ Overkill: Don't need SQL features |
| **PostgreSQL** | Full SQL database server | ❌ Too complex: Separate service to manage |
| **DynamoDB** | Managed cloud database | ❌ Expensive: Costs scale with usage |
| **Cassandra** | Distributed NoSQL | ❌ Over-engineered: Too complex for index data |

### Real-World Analogy

Think of BoltDB like a **filing cabinet**:
- **Each drawer** = a BoltDB file (e.g., one day's worth of index)
- **Folder labels** = keys (label combinations like `{app="web", env="prod"}`)
- **Documents in folders** = values (lists of chunk IDs)
- **Fast local access** = you can instantly grab any folder without network calls
- **Portable** = you can literally copy the filing cabinet to another office

### BoltDB in UDS Core Context

**Operational Benefits**:
- **No separate database to secure/patch/backup**
- **Kubernetes-friendly**: Just files in container volumes
- **Resource efficient**: Minimal memory/CPU overhead
- **Debugging**: Can inspect BoltDB files with simple Go tools

**Integration with UDS policies**:
- Works within UDS Core's resource constraints
- No additional network policies needed for database access
- Fits the "secure baseline" philosophy of minimal dependencies

**Key Insight**: Modern Loki (v2.0+) uses "Single Store" - both index files and chunk data go to the same object storage (like S3).

**How Single Store Works**:
```
Vector → Loki Ingester → Single S3 Bucket
                      ├── /chunks/        (log content)
                      └── /index/         (BoltDB files)
```

**Both stored in S3, but different mechanisms**:

1. **Index Files** (BoltDB Shipper):
   - Created locally as BoltDB files, then "shipped" to S3
   - Small files containing label metadata and chunk references
   - Compressed with gzip before upload to S3
   - Updated every 15 minutes to a few hours

2. **Chunk Files** (Log Content):
   - Compressed log data written directly to S3
   - Much larger files containing actual log text
   - Written as logs are ingested (more frequent)

### Why This Architecture is Fast

**Speed comes from local caching and different access patterns**:

1. **Local Index Cache**:
   - Loki downloads and caches BoltDB index files locally
   - Index lookups happen against local BoltDB files (very fast)
   - Index files sync from S3 to local cache directory

2. **Query Process**:
   ```
   Query Request → Local BoltDB Index (fast) → Get chunk IDs → Download chunks from S3 (slower)
   ```

3. **Different File Sizes**:
   - Index files: Small, cached locally, accessed frequently
   - Chunk files: Large, retrieved on-demand, accessed less frequently

### Legacy vs Modern Architecture

**Legacy Loki (pre-v2.0)**:
```
Index → Separate store (DynamoDB, Cassandra, Bigtable)
Chunks → Object storage (S3, GCS)
```

**Modern Loki (v2.0+)**:
```
Index → BoltDB files in S3 (with local caching)
Chunks → Compressed chunks in S3
```

**UDS Core Benefits**:
- **Simplified deployment**: Only need S3, no separate database
- **Cost reduction**: No DynamoDB/Cassandra hosting costs
- **Operational simplicity**: One storage system to manage
- **Better multi-tenancy**: Natural S3 bucket/path isolation

### Stream Management and Performance

**Stream Creation**: Each unique combination of labels creates a new stream
```yaml
# These create DIFFERENT streams:
{namespace="app", pod="web-1", level="info"}    # Stream A
{namespace="app", pod="web-1", level="error"}   # Stream B  
{namespace="app", pod="web-2", level="info"}    # Stream C
```

**Performance Implications**:
- **Too many streams** = high cardinality = poor performance (index bloat)
- **Too few streams** = inefficient queries (must scan large chunks)
- **Optimal strategy**: Keep label combinations meaningful but limited
- **Vector's role**: Smart labeling to balance searchability and performance

**Chunk Management**:
- Loki bundles log entries from same stream into compressed chunks
- Each chunk typically contains 1-10MB of compressed log data
- Chunks stored in object storage with predictable naming patterns
- Retention policies control when chunks are deleted from storage

**Backpressure Handling**:
- When Loki is overwhelmed, HTTP requests return error codes
- Vector buffers logs locally and implements retry with exponential backoff
- Prevents log loss during temporary Loki unavailability or object storage issues

Vector's configuration aligns with UDS Core's security model:

**Network Security**: 
- Respects UDS Core NetworkPolicies for egress to Loki
- Works within Istio service mesh constraints (both sidecar and ambient modes)

**Resource Management**:
- Configured with appropriate resource limits for baseline platform
- Optimized for multi-tenant environments where resources are shared

**Service Discovery**:
- Leverages Kubernetes API for automatic pod/container discovery
- Adapts to UDS Core's dynamic workload patterns

### Labels vs Content Strategy
- **Labels**: Used for indexing (e.g., `namespace`, `pod`, `container`, `app`)
- **Content**: Actual log messages (searched at query time)
- **Cardinality Control**: Keep unique label combinations low for performance
- **Best Practice**: Use consistent labeling strategy across all applications

### LogQL for Platform Troubleshooting

Common queries for platform engineers:

```logql
# All logs from a specific namespace
{namespace="[NAMESPACE]"}

# Error logs across the platform
{namespace=~".*"} |= "ERROR"

# Pod startup issues
{namespace="[NAMESPACE]", container="[CONTAINER]"} |= "failed"

# Rate of errors per application
rate({app="[APP-NAME]"} |= "error" [5m])
```

### Storage and Retention Considerations

- **Object Storage**: Integrates with S3, GCS, Azure Blob Storage
- **Retention Policies**: Configure based on compliance and cost requirements
- **Compaction**: Background optimization for long-term storage efficiency
- **Multi-tenancy**: Natural namespace isolation for customer separation

## Platform Engineering Benefits

### Unified Observability Experience
- **Single Pane of Glass**: Logs, metrics, and traces in Grafana
- **Correlation Capabilities**: Link alert metrics to detailed log context
- **Reduced Context Switching**: Everything in familiar Grafana interface

### Troubleshooting Efficiency  
- **Fast Incident Response**: Quick log queries during outages
- **Application Debugging**: Developers can self-service log access
- **Infrastructure Monitoring**: Platform-level log analysis and alerting

### Operational Scalability
- **Multi-tenant Ready**: Namespace-based isolation for customers
- **Cost Allocation**: Track log volume per tenant/application
- **Performance Monitoring**: Monitor log ingestion rates and query performance

## Common Troubleshooting Scenarios

### Vector Agent Issues
- **Symptom**: Missing logs from specific nodes or namespaces  
- **Investigation**: Check Vector daemonset status and node resources
- **Resolution**: Verify log collection configuration and permissions

### Loki Storage Problems
- **Symptom**: Query failures or slow performance
- **Investigation**: Check object storage connectivity and permissions
- **Resolution**: Verify backend storage configuration and network policies

### High Cardinality Issues
- **Symptom**: Poor query performance or high resource usage
- **Investigation**: Analyze label combinations and ingestion patterns  
- **Resolution**: Optimize labeling strategy and add label dropping rules

### Integration with UDS Core Components
- **Network Policy Conflicts**: Ensure Vector can reach Loki through UDS networking rules
- **Authentication Issues**: Verify Grafana-Keycloak integration for log access
- **Policy Violations**: Check if UDS Policy Engine blocks log collection pods

## Next Steps for Deep Dive

This document will be expanded to cover:
- Advanced LogQL queries and alerting strategies
- Performance tuning and capacity planning
- Integration patterns with other UDS Core components
- Specific troubleshooting playbooks
- Best practices for multi-tenant log management
- Security considerations and compliance requirements

## UDS Core Loki Configuration Analysis

### UDS Architecture Overview

**UDS Core Structure**:
- **Bundle**: Collection of functional layer packages (can be installed all-at-once or individually)
- **Functional Layer**: Individual Zarf packages grouped by functionality (e.g., `core-logging`)
- **Component**: Individual services within a functional layer (e.g., `loki`, `vector`)
- **Flavor**: Different image registries for varying security requirements (`upstream`, `registry1`, `unicorn`)

**Logging Functional Layer** (`core-logging`):
```yaml
components:
  - name: loki      # ← Log storage and querying
  - name: vector    # ← Log collection agent
```

### Key UDS Core Loki Configurations

Based on the provided `values.yaml`, here are the opinionated configurations:

#### **1. Storage Configuration**
```yaml
loki:
  storage:
    type: s3
    s3:
      endpoint: http://minio.uds-dev-stack.svc.cluster.local:9000
      secretAccessKey: uds-secret
      accessKeyId: uds
      s3ForcePathStyle: true
```
**Opinionated Decision**: Uses MinIO (S3-compatible storage) deployed within the cluster rather than external cloud storage
- **Benefit**: Self-contained, air-gapped friendly deployment
- **Implication**: Handles both BoltDB index files and chunk storage in same MinIO instance

#### **2. Single Store with Dual Schema Strategy**
```yaml
schemaConfig:
  configs:
    - from: 2022-01-11
      store: boltdb-shipper      # Legacy schema
      schema: v12
    - from: [dynamic-date]
      store: tsdb                # Modern schema  
      schema: v13
```
**Opinionated Decision**: Implements gradual migration from BoltDB to TSDB indexing
- **Benefit**: Allows seamless upgrades without data loss
- **Implication**: New installations use TSDB, existing installations migrate over time

#### **3. Security-First Approach**
```yaml
containerSecurityContext:
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
  allowPrivilegeEscalation: false
```
**Opinionated Decision**: Hardened security posture following zero-trust principles
- **Benefit**: Minimizes attack surface for regulated environments
- **Implication**: Aligns with UDS Core's "secure baseline" philosophy

#### **4. Resource Optimization for Baseline Platform**
```yaml
singleBinary:
  resources:
    limits:
      cpu: 100m
      memory: 256Mi
    requests:
      cpu: 100m  
      memory: 256Mi
```
**Opinionated Decision**: Conservative resource allocation
- **Benefit**: Ensures Loki runs on resource-constrained environments
- **Implication**: May need tuning for high-volume log scenarios

#### **5. Simplified Deployment Mode**
```yaml
deploymentMode: SimpleScalable
singleBinary:
  replicas: 0          # Disabled
```
**Opinionated Decision**: Uses SimpleScalable mode (read/write/backend separation) rather than single binary
- **Benefit**: Better performance and horizontal scaling capabilities
- **Implication**: More complex deployment but production-ready

#### **6. Air-Gap Friendly Configuration**
```yaml
analytics:
  reporting_enabled: false
```
**Opinionated Decision**: Disables telemetry that requires external connectivity
- **Benefit**: Works in completely disconnected environments
- **Implication**: No usage analytics sent to Grafana Labs

#### **7. Multi-Tenancy Disabled (Initially)**
```yaml
auth_enabled: false
```
**Opinionated Decision**: Single-tenant mode by default
- **Benefit**: Simpler initial deployment and troubleshooting
- **Implication**: All logs stored under "fake" tenant, can be changed later

#### **8. Conservative Query Limits**
```yaml
limits_config:
  split_queries_by_interval: "30m"
  allow_structured_metadata: false
query_scheduler:
  max_outstanding_requests_per_tenant: 32000
```
**Opinionated Decision**: Balanced performance vs resource consumption
- **Benefit**: Prevents runaway queries from overwhelming the system
- **Implication**: May need adjustment for high-query-volume scenarios

### Flavor-Based Image Strategy

**Three Security Tiers**:
1. **Upstream** (`docker.io`): Standard Docker Hub images for development
2. **Registry1** (`registry1.dso.mil`): DoD Iron Bank hardened images  
3. **Unicorn** (`quay.io/rfcurated`): RapidFort curated + FIPS-enabled images

**Security Progression**: Each tier provides additional hardening and compliance features
- **Loki Configuration**: Locate and analyze the primary Loki config file in UDS Core's Zarf package
  - Find the specific configuration parameters used in UDS Core deployment
  - Document how Vector→Loki→Grafana integration is configured
  - Examine storage configuration, retention policies, and resource limits
  - Review security settings and multi-tenancy configuration

- **Grafana-Loki Integration Investigation**: 
  - **Key Question**: Does UDS Core automatically configure Loki as a data source in Grafana?
  - Check Grafana provisioning configs in UDS Core Zarf packages
  - Look for datasource YAML files that pre-configure Loki connection
  - Investigate if there's automatic service discovery between Grafana and Loki
  - Document whether platform users need to manually add Loki datasource or if it's pre-configured
  - Examine any ConfigMaps, Secrets, or init containers that handle Grafana→Loki connectivity
  - **Benefit**: Understanding this prevents duplicate configuration and ensures proper platform delivery