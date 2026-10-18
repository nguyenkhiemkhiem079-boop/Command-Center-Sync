# COMMAND_CENTER_ARCHITECTURE_V2 — Full Fix delta

Source `552197b91b09c955d0fb48f96e329eba20b98f64`; evidence date18/10/2026. Supersedes earlier progress claims; full acceptance remains false.

Một controller và một SQLite Registry được giữ nguyên. ControlStore migrations bổ sung cùng DB; không tạo competing scheduler. Luồng: immutable knowledge/contract/workflow → atomic Wave/assignments → durable delivery outbox → worker ACK → checkpoints/Self-QA CLAIMED → independent verifier → Codex review → combined integration candidate → owner approval. Production verifier/owner principal chưa có nên phần promotion bị chặn.

Governance, worktree_manager, mission_recovery và cockpit là extensions của Registry hiện hành. Supervisor chạy deterministic mỗi 10 giây, không model polling, không tự dispatch/approve. Recovery giữ FROZEN sau uncertain timeout/restart. Staging fixture riêng port8878 không chứa credentials/DB production. Live8876 chưa thay thế.
