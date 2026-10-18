# Exact non-production CI bootstrap proposal — pending owner approval

Target proposed: integration/command-center-qa, private to Command Center development (repository itself currently public). Seed from reviewed full-fix candidate after local tests. No K-TOOL production ref is touched. Do NOT use current default dev branch as protected production by accident.

Requested settings for integration/command-center-qa: require pull requests; one owner approval; dismiss stale reviews; require last-push approval; require up-to-date head and check `Trusted base scope policy`; enforce admins; block force pushes/deletion; no bypass actors; no auto-merge. Keep token contents:read, no pull_request_target, no PR code with privileged secrets. Pin checkout immutable11bd719... verified upstream v4.2.2 tag.

Policy `.github/scope-policy.json` schema1 exists, approval_state=PENDING_OWNER_APPROVAL: intentionally fails closed. It grants no worker rights until owner approves exact reviewed policy on trusted base. CI-PILOT allows only ci-pilot; security/QA/workflows/shared-core protected. Policy loaded from PR base, never candidate. Only this narrow fixture assignment can pass; other tasks require separate reviewed contract/policy updates.

After owner approves exact seed commit/branch/settings: set policy approved only in trusted bootstrap under that approval; create protected target; open benign ci-pilot PR and hostile out-of-scope PR to observe actual checks. Record candidate SHA/run URL/job/artifacts. No hosted CI PASS exists yet. A CI scope check alone is not execution provenance or full build QA. If branch protections unavailable under repo plan, report exact API/UI failure and keep production integration blocked.
