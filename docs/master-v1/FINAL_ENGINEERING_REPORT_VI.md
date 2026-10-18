# BÁO CÁO KỸ THUẬT HỢP NHẤT — FULL FIX

Ngày18/10/2026. **Chưa nghiệm thu End-to-End toàn hệ thống.** Source hardening đã push vào development branch; live installation và dữ liệu hiện hành được bảo tồn. Candidate code `552197b91b09c955d0fb48f96e329eba20b98f64`, reviewed baseline `1f0f5e4a72e4bc028a8d2194fc00f82d3b391d5c`. Không sửa K-TOOL Revit production, không merge/release, không account rotation hoặc bypass tool denials.

## Kết quả chính

- Full regression Windows: **196 tests /173.942s/OK**. Đây là independent local Codex execution trong cùng OS principal, không phải production-trusted CI. Các focused QA01–08 khác mục tiêu đều có logs tại `evidence-full-fix/passes-verified`, source8a3b275. Candidate552197b bổ sung ba test backup/supervisor đã thực thi và có trong full regression.
- Hosted CI pilot thật: [PR1](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/1) SUCCESS, [PR2](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/2) FAILURE đúng kỳ vọng do OUT_OF_SCOPE/PROTECTED_PATH, exit2. Target bootstrap4380084 được duyệt, không production. Protection Save đang đợi GitHub Confirm access; không ghi protected khi API vẫn false.
- Live `http://127.0.0.1:8876/ui` vẫn sourcec377d10, hai khóa PILOT-ANTI01/02 FROZEN và credentials/worktrees giữ nguyên. Candidate staging8878 dùng fixture riêng, actual MCP45 tools và authenticated browser checks đạt. Không diễn giải fixture thành Anti thật.
- Crosswalk56: **9 IMPLEMENTED_AND_VERIFIED trong phạm vi local /42 PARTIAL /5 BLOCKED**. Việc một mục không còn MISSING không có nghĩa đạt toàn bộ contract. Xem từng giới hạn tại MASTER_FEATURE_CROSSWALK.md.

## Thay đổi theo Wave

W1: six-role backend, opaque principals, knowledge version/hash/provenance, risk classification, bound/expiring/once-only fixture approvals, tamper/spoof rejection, protected owner actions fail-closed. Trusted record thêm contract/workflow/verifier/approval bindings; fake SHA/tree/profile/artifact/CI rejected. Windows ACL helper removes broad ACE and refuses reparse ancestors. Existing token stores unchanged.

W2: same-Registry durable outbox, ACK/timeout/retry, dependency/barrier/steering governance; exact worktree root/branch/base/owner revalidation; wrong/shared worktrees rejected. No production dispatch based on fabricated runtime health. Local transaction14 tests exercise conflicts, failed combined QA, CAS and crash journals without changing Central on failure.

W3: verified source bundle/hash/log/epoch checkpoints; consolidated mission result; normalized repeated root cause freezes after3 rounds; actual process recovery drill23 checks; corrupt SQLite backup cannot receive integrity manifest; bounded deterministic periodic supervisor with no model polling/privilege promotion.

W4: original incremental Fleet Cockpit, three-layer identity UNKNOWN, controller DAG, safe timeline, read-only protected Approval Inbox, immutable recorded Git diff and frozen ownership inspector. Staging responsive Windows Chrome tests. AGY headless soft-denied logs rejected even exit0; keep SUPERVISED_IDE. No proof of two provider sessions from MCP tokens.

## Git và bằng chứng

Development branch `feature/full-fix-e2e-acceptance` pushed through552197b. Wave commits:711b6e8,9b171df,3832d7b,8b838a1; subsequent fixes e421816,c79e407,ef9bd67,8a3b275,552197b. Wave4 first regression had1 mock failure; corrected in e421816 and subsequent full suites pass. Original FAIL log preserved; no history rewrite.

`evidence-full-fix/candidate-source-inventory.json` lists 43 affected source files with hashes relative to baseline. `git diff 1f0f5e4a72e4bc028a8d2194fc00f82d3b391d5c 552197b91b09c955d0fb48f96e329eba20b98f64` reproduces source diff; report docs are a later commit. Hosted runs39133452978/39133453324 JSON contain actual candidate/job/step status. Local logs, screenshots and JSON retained in workspace; checksums manifest accompanies handover. Private SQLite/token files are not delivery artifacts.

## Migration, rollback và vận hành

Candidate not applied to8876. `pwsh -NoProfile -File UPGRADE_EXISTING_MCP.ps1` actual DRY_RUN PASS. Apply requires separately approved exact candidate and verified stopped8876 listener; script stops no process, uses existing venv, integrity-checked SQLite backup, protected source-before and hash manifest, copies only listed source/assets and retains private data. Startup migration is additive; existing active/frozen records are not cleared.

Rollback after a future approved update: stop only verified coordinator process; restore recorded old source from protected source-before by manifest; retain current DB unless isolated restore drill proves compatible and owner approves exact DB recovery. Never overwrite a live DB or silently downgrade schema. Launch approved interpreter/roles/db paths; verify localhost listener, integrity, roles, existing locks and stdio adapters before reopening worker dispatch.

## Cổng còn thiếu và bước mở khóa

1. Chủ dự án nhập mã trực tiếp tại tab GitHub Confirm access và Verify; Codex lưu/đọc lại exact approved protection, giữ hai PR không merge. Approval đã có, chỉ thiếu platform authentication.
2. Protected independent verifier/owner principal thực sự: phê duyệt thiết kế/entrypoint pin protected workflow source, candidate SHA, test profile/suite and artifacts. Scope check alone không chứng nhận full QA. Same-Windows-user files/hashes không bảo đảm worker không giả bằng chứng. Production acceptance vẫn disabled.
3. Operator mở hai Antigravity sessions bằng cơ chế được hỗ trợ, cung cấp IDs không bí mật; kiểm chứng time overlap, roles/worktrees, permitted ACK/source edits/self-QA/checkpoints/Codex feedback. Giữ `BLOCKED_TWO_ACCOUNT_TEAMWORK` tới khi có chứng cứ; không kết luận impossible.
4. Candidate staging review và approval riêng trước upgrade8876. Native sessions, real subprocess subagents, Windows restart, pilot2 repo/branch, Revit2025 host và long-running mission chưa thực thi/duyệt. Không reboot máy có Revit đang mở. Không production merge/release nếu chưa có approval cụ thể.

Pilot1 local test harness đạt phạm vi logical orchestration/Git; không phải native Teamwork. Pilot2–4 chưa nghiệm thu. FINAL_GATE_MATRIX.json ghi riêng local execution và full gate. Thành công196 tests không thay thế các cổng bị chặn.
