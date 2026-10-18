# P0 blockers and dependency order

1. .github/scope-policy.json MISSING while scope-gate references it. Current required workflow cannot certify changes. Need deny-by-default versioned policy schema, immutable trusted-base checker and owner-approved integration base; no bootstrap policy from worker head.
2. trust_vault production path deliberately BLOCKED; no independently protected verifier. Local hashes do not prove trusted execution. Add adapter validation/tests, keep production acceptance disabled until genuine hosted checks tested.
3. Only three authenticated bearer identities currently; six-role principals and risk/expiring once-only approvals incomplete. Preserve credential stores; no automatic owner credential issuance.
4. Provisioner ACL handling does not prove removal of preexisting explicit broad ACEs; legacy upgrade file inventory incomplete. Inspect and fix source/tooling before future rollout, preserve live token values.
5. Human Request types/deadlines exist; contract knowledge taxonomy, approval consumption and protected owner authentication need completion in same Registry.
6. Official native Teamwork start/monitor and two-session account isolation unverified. User chose supervised manual launch; no bypass. This does not prove technical impossibility.
7. Integration branch/protection/PR CI trial requires explicit owner approval. Exact settings will be prepared before asking; do not configure protection or merge by inferred admin rights.

No component is rebuilt because its name changed; test contracts and remaining dependency evidence drive implementation. UI changes must stage before approved live rollout. Windows reboot requires operator approval and is not attempted during open Revit work.
