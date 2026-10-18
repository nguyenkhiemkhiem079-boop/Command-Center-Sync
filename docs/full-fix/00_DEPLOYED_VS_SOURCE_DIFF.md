# Deployed vs source

Source HEAD1f0f5e4 vs deployed c377d10. Exact byte hashes differ for59files initially; 53 are line-ending-only (CRLF working checkout versus Git archive). Canonical Git blob/content comparison leaves 6 actual source/document deltas below. Runtime Python source has no semantic drift at audit time. Manifest preserves raw and canonical states; no file was rewritten to normalize line endings.

- SOURCE_ONLY: docs/master-v1/DEPLOYMENT_ACCEPTANCE_VI.md
- DIFFERS: docs/master-v1/FINAL_ENGINEERING_REPORT_VI.md
- DIFFERS: docs/master-v1/FINAL_GATE_MATRIX.json
- DIFFERS: docs/master-v1/SHA256SUMS
- SOURCE_ONLY: docs/master-v1/deployment-dashboard.png
- SOURCE_ONLY: docs/master-v1/deployment-live-validation.json
