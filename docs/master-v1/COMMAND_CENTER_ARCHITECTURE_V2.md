# Kiến trúc V2 — kế hoạch delta

Một controller và authoritative Task/Workflow Registry hiện có. Không thêm scheduler cạnh tranh. cc_* mở rộng cùng SQLite để tương thích legacy; transaction journal riêng chỉ là nhật ký thao tác Git, không phải task authority thứ hai. Snapshot Dashboard chỉ đọc API, không truy cập SQLite từ browser.

Boundary 1: bearer MCP role -> server role check -> approved contract/revision -> dispatcher + exclusive locks -> exact worktree. Boundary 2 còn BLOCKED: independent trusted QA principal -> immutable check/candidate binding -> Codex review -> owner approval -> protected integration CAS. Shared Windows principal là LOGICAL_ONLY; không local hash nào thay trust boundary.

Thứ tự theo dependency:
1. W1 governance (ưu tiên provisioner explicit ACL audit và upgrade script legacy-file inventory trước deployment): typed requests/migrations (delta đầu), role model/permission schema, risk engine, protected QA principal/policy và audit anchoring. Thiết kế không tự cấp credentials hoặc owner power.
2. W2 dispatcher outbox + ACK timeout/retry, generic worktree manager, durable parent continuation, PR/branch required checks. Phụ thuộc W1 pinned contract và verified policy.
3. W3 supervisor liveness/watchdog, verified checkpoint inventory, mission aggregator, combined regression adapter. Không autoapprove khi mất lead; không replay ambiguous side effects.
4. W4 identity inspector/session event normalization, authenticated event stream, safe diff/artifact views, DAG graph/approval inbox. Native capabilities phải thử thật trước khi phụ thuộc điều khiển.
5. Pilot1 hai runtime thật, rồi owner duyệt repo/branch cho pilot2; Revit2025 thật cho pilot3; pilot4 dài sau các gate trước.

Chỉ source development và isolated QA được làm trước khi setup xong. Deployment, protected security permissions và production integration là cổng riêng. Mỗi slice có reviewable commit, tests và evidence; không rewrite working modules.
