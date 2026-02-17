# Mattermost SSO “Misdirected Request” on iPhone (Istio gateway 421)

## TL;DR
On iPhone (Chrome/iOS → WebKit), the browser **reused an existing HTTP/2 TLS connection** that was established with **SNI = `chat.uds.dev`** to send a request whose HTTP/2 **`:authority` = `sso.uds.dev`** (or vice versa). An Istio gateway **EnvoyFilter** (`istio-system/misdirected-request`) intentionally rejects this **SNI/authority mismatch** by returning **HTTP 421** with the body `Misdirected Request`.

Deleting that EnvoyFilter immediately unblocked iPhone access.

---

## Observed symptoms
- From iPhone Chrome:
  - Visit `https://chat.uds.dev`
  - Click “Login with SSO”
  - Redirect to `https://sso.uds.dev/...`
  - Browser shows black page with text: **`Misdirected Request`** (no status code shown in UI)
- From MacBook (Chrome/Brave on macOS): workflow consistently worked.

---

## Key concepts (client side)

### iOS Chrome / Brave uses WebKit
On iOS, third-party browsers must use **WebKit** under the hood (Apple policy). This matters because WebKit’s connection reuse behavior can differ from macOS Chromium.

### HTTP/2 connection coalescing
With HTTP/2, clients may reuse a single TCP+TLS connection for requests to multiple hostnames if it believes they’re “the same server”, commonly when:
- both hostnames resolve to the same IP
- the server certificate is valid for both hostnames
- ALPN negotiated `h2`

This can produce an **SNI/authority mismatch** if the connection was created for one hostname (SNI fixed at handshake), but later carries requests for another hostname (`:authority` varies per request).

### SNI vs `:authority`
- **SNI** (Server Name Indication) is a **TLS ClientHello extension** used during the TLS handshake. It is set once per TLS connection.
- **`:authority`** is the HTTP/2 pseudo-header that represents the request host (roughly the HTTP/1.1 `Host` equivalent). It is set per request.

---

## What we observed in the cluster

### DNS
Both names resolved to the same address:
- `chat.uds.dev` → `192.168.1.96`
- `sso.uds.dev` → `192.168.1.96`

### Tenant gateway access logs: definitive 421
Tenant ingressgateway logs showed **HTTP/2 421** responses with `lua_response`, for example:

- Request path was Keycloak auth endpoint:
  - `GET /realms/uds/protocol/openid-connect/auth?...redirect_uri=https://chat.uds.dev/signup/openid/complete...`
- Response:
  - **`421`**
  - **`lua_response`**
- Log indicated host/authority `sso.uds.dev` while the connection/serverName context was `chat.uds.dev`.

This matches the iPhone page showing `Misdirected Request`.

### EnvoyFilter that generated the 421
`kubectl -n istio-system get envoyfilter misdirected-request -o yaml`

This filter inserted a Lua HTTP filter at **GATEWAY** context. The Lua logic:
- reads `requestedServerName()` (TLS SNI)
- reads `:authority` (HTTP host)
- if they don’t match, returns:
  - `:status = 421`
  - body: `Misdirected Request`

This is a guardrail to prevent requests for one hostname from being sent over a connection established for another hostname.

### Other (likely unrelated) signal
One request appeared as:
- `POST /api/v4/cloud/check-cws-connection` → `500`
This is probably unrelated to the 421/SNI mismatch but was seen during the same window.

---

## Changes attempted (did not fix)
We tried eliminating differences in Istio Gateway TLS servers/filter chains:

1) Noted tenant gateway originally had separate 443 servers:
   - `sso.uds.dev` → `tls.mode: OPTIONAL_MUTUAL`
   - `*.uds.dev` → `tls.mode: SIMPLE`

2) Patched wildcard `*.uds.dev` 443 to `OPTIONAL_MUTUAL`.

3) Restarted tenant ingressgateway deployment to flush connections.

4) Removed dedicated `sso.uds.dev` servers so only `*.uds.dev` remained.

Even after these changes + restarts, iPhone still hit `Misdirected Request`.

Reason: the 421 was produced by the **global EnvoyFilter**, independent of those gateway server definitions.

---

## Fix applied (worked)
**Deleted the EnvoyFilter** and restarted the tenant ingressgateway:

```bash
kubectl -n istio-system delete envoyfilter misdirected-request
kubectl -n istio-tenant-gateway rollout restart deploy/tenant-ingressgateway
kubectl -n istio-tenant-gateway rollout status deploy/tenant-ingressgateway --timeout=120s
```

Result: iPhone SSO flow started working immediately.

---

## Why macOS worked but iPhone didn’t (high-level)
- macOS Chrome/Brave (Chromium network stack) didn’t trigger the problematic cross-host reuse pattern (or did so less aggressively).
- iOS WebKit reused the h2 connection across `chat` and `sso` because they shared IP + cert.
- The EnvoyFilter intentionally rejects SNI/authority mismatches (421).

---

## Long-term options (if we want to keep the guardrail)
Instead of deleting the EnvoyFilter, options include:

1) **Separate IPs / gateways** for `chat.uds.dev` and `sso.uds.dev`
   - Prevents coalescing because connections won’t share the same destination.

2) **Disable HTTP/2** on the gateway
   - Removes the coalescing behavior (at the cost of h2 benefits).

3) **Scope/relax the EnvoyFilter**
   - Apply it only to the specific hosts where it’s needed, or
   - Adjust matching logic/allowlists so expected cross-host behaviors aren’t blocked.

---

## Useful commands

### Confirm DNS
```bash
dig +short chat.uds.dev A
dig +short sso.uds.dev A
```

### Watch tenant gateway access logs
```bash
kubectl -n istio-tenant-gateway logs -l app=tenant-ingressgateway --since=10m | egrep '421|Misdirected|sso\.uds\.dev|chat\.uds\.dev'
```

### Inspect the EnvoyFilter
```bash
kubectl -n istio-system get envoyfilter misdirected-request -o yaml
```
