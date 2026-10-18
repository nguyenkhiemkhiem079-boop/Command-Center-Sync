# Router source audit — provider routing versus native Teamwork

Audit date: 2026-10-18. Agent-reach GitHub/dev route was applied. `gh` and
`agent-reach` were absent from PATH; read-only Git fallback succeeded. Repositories
were shallow-cloned beneath the Windows TEMP directory; no source from them was
executed, installed, imported or copied into K-TOOL. No router OAuth flows,
credential imports, MITM/DNS changes or account rotation were performed.

## Immutable observations

| Repository | Observed HEAD | License |
|---|---|---|
| decolua/9router | `87a74e1bda3677193c6f71a7e2100c90311f0689` | MIT, LICENSE lines 1–3 |
| htilssu/n9router | `baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f` | MIT, LICENSE lines 1–3 |

9router exposes an OpenAI-compatible API and stores provider connection records.
Its [provider route, lines 50–84](https://github.com/decolua/9router/blob/87a74e1bda3677193c6f71a7e2100c90311f0689/src/app/api/providers/route.js#L50-L84)
lists connections and begins connection creation. Its
[chat-completions route, lines 1–35](https://github.com/decolua/9router/blob/87a74e1bda3677193c6f71a7e2100c90311f0689/src/app/api/v1/chat/completions/route.js#L1-L35)
initializes protocol translators and forwards requests to its chat handler. These
are account/API-routing capabilities; they do not create independent native
Antigravity Teamwork supervisors or worktrees.

n9router's [README, lines 6–10](https://github.com/htilssu/n9router/blob/baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f/README.md#L6-L10)
identifies its added MITM token-rotation feature. Its
[README, lines 350–426](https://github.com/htilssu/n9router/blob/baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f/README.md#L350-L426)
describes account pools, DNS interception and rotation after quota errors. Its
[token pool implementation, lines 282–354](https://github.com/htilssu/n9router/blob/baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f/src/mitm/tokenPool.js#L282-L354)
reads provider connection records and filters available accounts; its
[selection logic, lines 454–501](https://github.com/htilssu/n9router/blob/baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f/src/mitm/tokenPool.js#L454-L501)
implements account ordering/sticky behavior. This path conflicts with the explicit
restriction against rotating consumer accounts to bypass quota. It was not used.

License sources: [9router LICENSE](https://github.com/decolua/9router/blob/87a74e1bda3677193c6f71a7e2100c90311f0689/LICENSE#L1-L3),
[n9router LICENSE](https://github.com/htilssu/n9router/blob/baaf27e6748fe71a5f59a1dd12e5be7bb8fe3d3f/LICENSE#L1-L3).
Licensing does not establish provider authorization or operational suitability.

## Decision

Neither repository supplies evidence of two independently authenticated native
Teamwork sessions merely by registering two provider accounts. Provider routing
could be a separately authorized API integration in future, but cannot substitute
for the current native Teamwork requirement. The K-TOOL runtime adapter implements
no router credential discovery or account-pool behavior.

API-backed coding workers additionally need an explicitly authorized endpoint,
model/tool contract, API credential, tool execution sandbox and budget. None was
supplied for this task. Their runtime status is unavailable; no consumer token
was reused or probed. No claim about authenticated API availability is made.

## Reproducible read-only checks

```powershell
git ls-remote https://github.com/decolua/9router.git HEAD
git ls-remote https://github.com/htilssu/n9router.git HEAD
# In disposable TEMP checkouts, compare rev-parse HEAD with the pins above.
git rev-parse HEAD
rg -n 'getProviderConnections|createProviderConnection' src/app/api/providers/route.js
rg -n 'providerConnections|round-robin|sticky' src/mitm/tokenPool.js
```

Later HEAD values may differ. Reproduce code observations against the pinned
commits rather than silently updating the evidence. This is a scoped source
inspection, not a full security audit or an executed router benchmark.
