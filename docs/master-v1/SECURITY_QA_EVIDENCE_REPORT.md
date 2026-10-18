# Security QA evidence

Baseline e80e26f: 151/151 local regression PASS; log ../qa/final-regression.txt. Protected CI acceptance vẫn BLOCKED; fake SHA, mismatched tree/paths/profile, stale evidence và synthetic CI bị từ chối. LOCAL_VERIFIED chỉ consistency, không chứng minh command execution bởi independent principal.

Human Request delta: test_human_requests 4/4 PASS; migration giữ legacy rows, deadline canonical/reject naive+past, expired decisions deny, worker/checkbox cannot resolve, resolved request cannot replay. Test owner callback là TEST_FIXTURE cho persistence, không chứng minh production owner authentication. Full regression delta: 155/155 PASS, 114.168s, log full-regression.txt.

Còn thiếu: six-role identity registry, risk classifier, tamper-evident external audit anchor, protected principal and workflow/policy. Không đưa token stores/live SQLite vào Git.

Read-only independent agent audit phát hiện: provisioner hiện /inheritance:r và /grant:r không chứng minh đã loại bỏ mọi explicit broad ACE; chưa kết luận actual token files đang có broad ACL. Upgrade script còn legacy-file inventory, không được dùng nó như full V2 deployment procedure. Những việc này được giữ PARTIAL và ưu tiên trước rollout; không sửa credentials hoặc ACL thật trong đợt này.
