---
tags: [kubernetes, istio, envoy, prometheus, alertmanager, mattermost, monitoring, alerting, networkpolicy, troubleshooting]
---

# Alerting on HTTP 421 from an Istio/Envoy gateway (Prometheus + Alertmanager + Mattermost)

This write-up captures the steps to:

1) scrape Envoy/Istio request metrics from a gateway,
2) create a Prometheus alert for HTTP **421 (Misdirected Request)**, and
3) deliver that alert to Mattermost.

All examples are sanitized per the repo’s Ground Rules. Replace placeholders (e.g., `[NAMESPACE]`, `[GATEWAY-POD]`, `[DOMAIN-NAME]`, `[WEBHOOK-URL]`) with real values for your environment.

## Background / why 421 matters

HTTP 421 (“Misdirected Request”) is commonly emitted by an L7 proxy (Envoy) when the request is routed to a listener/virtual host that does not match the request’s authority/host/SNI expectations.

In practice, it’s a useful canary signal that:

- a gateway filter/behavior that enforces host/SNI matching is enabled, and/or
- a client is sending an unexpected Host/SNI combination.

## Step 1 — Confirm the gateway exposes Envoy Prometheus stats

Even when the proxy image is “distroless” (no shell), you can validate the Envoy Prometheus endpoint via port-forward:

```bash
kubectl -n [GATEWAY-NAMESPACE] port-forward pod/[GATEWAY-POD] 15090:15090
curl -sf http://localhost:15090/stats/prometheus | head
```

If you see Prometheus text output, Envoy stats are available.

## Step 2 — Ensure Prometheus is scraping the gateway

If your platform has a broad PodMonitor that relies on pod annotations (e.g., `prometheus.io/port`), gateway pods may not match out-of-the-box.

A simple, explicit solution is to add a dedicated PodMonitor for the gateway that scrapes the Envoy stats port.

### Example: dedicated PodMonitor for the gateway

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: gateway-envoy-stats
  namespace: [GATEWAY-NAMESPACE]
spec:
  selector:
    matchLabels:
      # label(s) that uniquely select your gateway pods
      app: [GATEWAY-APP-LABEL]
  podMetricsEndpoints:
    - port: http-envoy-prom
      path: /stats/prometheus
      interval: 15s
      scrapeTimeout: 10s
      scheme: http
```

Notes:
- `http-envoy-prom` is a common container port name for Envoy Prometheus stats (often 15090), but confirm in your gateway pod spec.
- Use label selectors that match only the intended gateway pods.

## Step 3 — Find the metric and write the query

In this setup, gateway-exported metrics included `istio_requests_total` with a `response_code` label.

### “Any 421 occurred recently” query

Count of 421s in the last 5 minutes:

```promql
sum(increase(istio_requests_total{
  source_workload_namespace="[GATEWAY-NAMESPACE]",
  source_workload="[GATEWAY-WORKLOAD]",
  response_code="421"
}[5m]))
```

- `increase()` returns a **count** over the time window.
- This is typically easiest to reason about for “single occurrence” alerting.

## Step 4 — Create an alert rule

### Example PrometheusRule

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: gateway-421
  namespace: [PROMETHEUS-RULES-NAMESPACE]
spec:
  groups:
  - name: gateway
    rules:
    - alert: GatewayMisdirectedRequest421
      expr: |
        sum(increase(istio_requests_total{
          source_workload_namespace="[GATEWAY-NAMESPACE]",
          source_workload="[GATEWAY-WORKLOAD]",
          response_code="421"
        }[5m])) > 0
      for: 0m
      labels:
        severity: warning
      annotations:
        summary: "Gateway returned HTTP 421 (Misdirected Request)"
        description: "At least one 421 response was observed from the gateway in the last 5 minutes. This can indicate a host/SNI mismatch or an enabled gateway filter."
```

## Step 5 — Deliver alerts to Mattermost

### Recommended approach

Use **Alertmanager → Mattermost Incoming Webhook**.

Mattermost webhooks are compatible with Alertmanager’s `slack_configs` format.

### Example receiver + route snippet

```yaml
receivers:
- name: "null"
- name: mattermost
  slack_configs:
  - api_url: "[WEBHOOK-URL]"
    username: "alertmanager"
    send_resolved: true
    title: "[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}"
    text: |-
      *Severity:* {{ .CommonLabels.severity }}
      *Namespace:* {{ .CommonLabels.namespace }}
      {{ range .Alerts -}}
      - {{ .Annotations.summary }}
        {{ .Annotations.description }}
      {{ end }}

route:
  receiver: "null"
  routes:
  - matchers: [alertname = "GatewayMisdirectedRequest421"]
    receiver: mattermost
  - matchers: [alertname = "Watchdog"]
    receiver: "null"
```

Important: if Alertmanager config is managed by Helm/Operator, editing generated Secrets is not durable.
For permanence, wire the receiver/route into chart values or the platform’s config mechanism.

## Step 6 — NetworkPolicy: allow Alertmanager egress to the webhook path

In locked-down clusters, Alertmanager may not be allowed to reach the webhook destination.

If your setup routes `[DOMAIN-NAME]` through a gateway (via ServiceEntry/DNS), Alertmanager may effectively be connecting to an in-cluster gateway service on TCP/443.

### Example NetworkPolicy (allow egress from Alertmanager → gateway on 443)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-alertmanager-egress-webhook-via-gateway
  namespace: [ALERTMANAGER-NAMESPACE]
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: alertmanager
  policyTypes: [Egress]
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: [GATEWAY-NAMESPACE]
      podSelector:
        matchLabels:
          app: [GATEWAY-APP-LABEL]
    ports:
    - protocol: TCP
      port: 443
```

## Troubleshooting checklist

- Prometheus → **Status → Targets**: confirm the gateway scrape target is `UP`.
- Prometheus → **Graph**: confirm `increase(istio_requests_total{...response_code="421"}[5m])` returns >0 after reproduction.
- Alertmanager logs: look for notify failures (connection reset/refused/timeouts).
- ServiceEntry / routing: verify `[DOMAIN-NAME]` resolves as expected inside the mesh.
- NetworkPolicy: ensure egress from Alertmanager namespace/pods to the gateway/webhook path is explicitly allowed.
