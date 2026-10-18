# Contract & Permission schema

Hiện tại: actor CODEX/ANTI-01/ANTI-02, OWNER direct verification hook; không có đủ six-role principal registry. Dự kiến Owner/Operator, CODEX_LEAD, ANTI_WORKER, SUBAGENT, TRUSTED_QA_RUNNER, READ_ONLY_OBSERVER. Mọi unknown role/action mặc định deny. Không map worker string tự khai thành privilege. Subagent lấy intersection parent scope/tools/resources.

Contract = immutable id/content hash + approved status + acceptance identifiers + baseline flag. Workflow revision pins contract hashes. Assignment pins mission/wave/team/owner/repo/base/allowed/readonly/forbidden/resources/dependencies/acceptance/revision/epoch. Cần bổ sung explicit required_outputs/review_policy và provenance taxonomy.

Human Requests schema v2 (additive): giữ cc_human_requests rows và id cũ; thêm nullable deadline, decided_at; cc_meta human_requests_schema_version=2. Types mới INPUT_REQUIRED, DIRECTION_REQUIRED, PERMISSION_REQUIRED, CONTRACT_CHANGE, MERGE_APPROVAL, RELEASE_APPROVAL; bốn type legacy giữ nguyên. Deadline timezone-aware, UTC canonical, phải ở tương lai khi tạo; expired resolution deny. Idempotent request hash includes normalized deadline khi có. Resolution once-only, owner verifier default deny; response không là permission grant, không merge/release side effect.

Migration chạy transaction BEGIN IMMEDIATE trên DB copy/tests; chưa áp dụng live installation. Older legacy rows giữ deadline NULL. Rollback không drop fields; binary cũ dùng explicit columns, không downgrade live DB bằng xóa dữ liệu. Backup/restore isolated trước mọi upgrade được owner duyệt. Chưa cung cấp general migration framework cho tất cả components.
