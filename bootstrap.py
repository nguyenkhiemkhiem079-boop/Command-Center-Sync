"""One-time setup; do not check private/ into Git."""
import json
from pathlib import Path
import secrets
from registry import Registry,hash_token

root=Path(__file__).resolve().parent
priv=root/'private'
priv.mkdir(exist_ok=True)
roles_file=priv/'roles.json'
if roles_file.exists():
    raise SystemExit('Already provisioned. Do not overwrite role tokens; see docs/RESET.md.')
tokens={role:secrets.token_urlsafe(40) for role in ('CODEX','ANTI-01','ANTI-02')}
roles={role:hash_token(token) for role,token in tokens.items()}
roles_file.write_text(json.dumps(roles,indent=2),encoding='utf-8')
(priv/'TRANSFER-TOKENS-DELETE-AFTER-INSTALL.txt').write_text(
    '\n'.join(f'{role}={token}' for role,token in tokens.items())+'\n',encoding='utf-8')
Registry(priv/'registry.db')
print('Created private/roles.json (HASHES), private/registry.db, and ONE-TIME TRANSFER TOKENS.')
print('Protect private/ with Windows NTFS ACL; never commit/copy credentials to AI or Git.')
print('Copy each token to the corresponding Windows user via scripts/install-client.ps1, then DELETE transfer token file.')
