# CI pilot thực tế — 18/10/2026

Chủ dự án duyệt nhánh và CI pilot trong cuộc trò chuyện. Không có quyền merge/release và không thay đổi default branch.

## Source và kết quả

- Nhánh `integration/command-center-qa` tạo từ `711b6e8f97688de3711a533ef85fa9231b5d4a00`.
- Bootstrap được duyệt `4380084a63c6592b0eac4c9415bbd26c155877f9`: chỉ đổi policy từ PENDING_OWNER_APPROVAL sang OWNER_APPROVED; CI-PILOT chỉ được sửa `ci-pilot/`.
- [PR #1](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/1), candidate `77aae61b147b15a40c7d852d4f6b903c4071afc5`: [run 39133452978](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/actions/runs/39133452978), job `117693123378`, actual conclusion SUCCESS.
- [PR #2](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/pull/2), candidate `509a021c643d04b4489be60a2609e80d017a7147`: [run 39133453324](https://github.com/nguyenkhiemkhiem079-boop/Command-Center-Sync/actions/runs/39133453324), job `117693124567`, actual conclusion FAILURE, exit 2. Logs ghi `OUT_OF_SCOPE` và `PROTECTED_PATH: tests/ci_scope_violation_probe.txt`. Negative test đạt kỳ vọng; run không được gọi PASS.

## Protection đã xác minh

Ruleset ID `25346465`, enforcement `active`, target đúng `refs/heads/integration/command-center-qa`, bypass list rỗng. Bắt buộc PR, 1 review, dismiss stale approvals, approval lần push cuối, check `Trusted base scope policy` từ GitHub Actions app, branch up-to-date; block force push và deletion. Classic rule cũng đặt PR/review/required-check; giao diện xác nhận rule này được ruleset bao phủ. PR #1 hiện có 1/1 check pass nhưng merge vẫn disabled vì thiếu review; message nêu cần approval khác người push. Không có merge.

Direct-push probe commit `485896c49428862c70c8a4814f2680aeaae82362` bị GitHub từ chối (exit1, GH013): required status check chưa có cho SHA và changes must be made through PR. Probe không cập nhật protected ref. Bằng chứng raw trong `evidence-full-fix/direct-push-attempt.txt`.

Evidence ngoài Git: `evidence-full-fix/ci-pilot-branch.json`, `ci-run-39133452978.json`, `ci-run-39133453324.json`, `ci-negative-dom.txt`, `ci-negative.png`, `direct-push-attempt.txt`, GitHub UI ruleset/PR merge-status observation.

## Giới hạn tin cậy

Đây là hosted scope validation thật, không phải full combined build/test hoặc trusted production attestation. Workflow pull_request vẫn có rủi ro bị PR sửa workflow; check name/app không đủ pin workflow source. Production acceptance tiếp tục fail-closed. Đề xuất protected manual verifier trong development branch chưa được owner duyệt/kích hoạt. Không tự đổi default branch, thêm privileged secrets, merge PR hay release.
