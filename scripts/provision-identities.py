"""Supervisor-only local migration of existing KTOOL credentials; never Google auth.

Does not bootstrap, rotate credentials, alter roles.json, or overwrite a token file.
Same Windows principal remains LOGICAL_ONLY regardless of ACLs.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess


def provision(root, appdata):
    roles=json.loads((root/'private/roles.json').read_text(encoding='utf-8'))
    transfer=root/'private/TRANSFER-TOKENS-DELETE-AFTER-INSTALL.txt'
    credentials=dict(line.split('=',1) for line in transfer.read_text().splitlines() if '=' in line)
    if set(roles)!=set(credentials) or set(roles)!={'CODEX','ANTI-01','ANTI-02'}:
        raise RuntimeError('Existing role/transfer inventory mismatch; manual recovery required')
    principal=subprocess.check_output(['whoami'],text=True).strip()
    outputs=[]
    for role in ('CODEX','ANTI-01','ANTI-02'):
        token=credentials[role]
        if hashlib.sha256(token.encode()).hexdigest()!=roles[role]:
            raise RuntimeError('Existing credential does not match registry role')
        directory=appdata/'KTOOLMCP/identities'/role
        directory.mkdir(parents=True,exist_ok=True)
        result=subprocess.run(['icacls',str(directory),'/inheritance:r','/grant:r',
                               principal+':(OI)(CI)F','SYSTEM:(OI)(CI)F'],capture_output=True)
        if result.returncode: raise RuntimeError('Identity ACL failed')
        target=directory/'client_token.txt'
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=roles[role]:
                raise RuntimeError('Existing identity credential conflict; refusing overwrite')
            action='PRESERVED'
        else:
            with target.open('x',encoding='utf-8') as output: output.write(token)
            action='COPIED_EXISTING'
        outputs.append({'identity':role,'credential_reference':str(target),'action':action,'backend_hash_matches':True})
    return {'isolation_level':'LOGICAL_ONLY','credentials':outputs,'rotation':False,'registry_overwritten':False}

if __name__=='__main__':
    if os.name!='nt' or not os.environ.get('APPDATA'):
        raise SystemExit('Run locally as authorized Windows supervisor')
    root=Path(__file__).resolve().parents[1]
    print(json.dumps(provision(root,Path(os.environ['APPDATA'])),indent=2))
