# CI pilot thực tế — 18/10/2026

Chủ dự án duyệt nhánh và CI pilot trong cuộc trò chuyện. Không có quyền merge/release và không thay đổi default branch.

## Source và kết quả

- Nhánh `integration/command-center-qa` tạo từ `711b6e8f97688de3711a533ef85fa9231b5d4a00`.
- Bootstrap được duyệt `4380084a63c6592b0eac4c9415bbd26c155877f9`: chỉ đổi policy từ PENDING_OWNER_APPROVAL sang OWNER_APPROVED; CI-PILOT chỉ được sửa `ci-pilot/`.
- [PR #1](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/1), candidate `77aae61b147b15a40c7d852d4f6b903c4071afc5`: [run 39133452978](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/actions/runs/39133452978), job `117693123378`, actual conclusion SUCCESS.
- [PR #2](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/2), candidate `509a021c643d04b4489be60a2609e80d017a7147`: [run 39133453324](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/actions/runs/39133453324), job `117693124567`, actual conclusion FAILURE, exit 2. Logs ghi `OUT_OF_SCOPE` và `PROTECTED_PATH: tests/ci_scope_violation_probe.txt`. Negative test đạt kỳ vọng; run không được gọi PASS.

## Protection

Đã điền đúng tên nhánh, PR bắt buộc, 1 approval, dismiss stale, approval lần push cuối, required check `Trusted base scope policy` từ GitHub Actions, up-to-date, no bypass. Force push/deletion không được bật. Khi Save, GitHub yêu cầu Confirm access (sudo mode). Tại thời điểm ghi báo cáo, đang chờ chủ dự án nhập mã trực tiếp trên GitHub; public API vẫn cho `protected:false`. Không ghi protection PASS khi chưa lưu.

Evidence ngoài Git: `evidence-full-fix/ci-pilot-branch.json`, `ci-run-39133452978.json`, `ci-run-39133453324.json`, `ci-negative-dom.txt`, `ci-negative.png`, `github-confirm-access.png`.

## Giới hạn tin cậy

Đây là hosted scope validation thật, không phải full combined build/test hoặc trusted production attestation. Workflow pull_request vẫn có rủi ro bị PR sửa workflow; check name/app không đủ pin workflow source. Production acceptance tiếp tục fail-closed. Đề xuất protected manual verifier trong development branch chưa được owner duyệt/kích hoạt. Không tự đổi default branch, thêm privileged secrets, merge PR hay release.
