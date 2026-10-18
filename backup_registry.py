"""Online-consistent SQLite snapshot, no credentials included."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import datetime,timezone


def backup(db_file:Path, backup_dir:Path):
    db_file=db_file.resolve(strict=True)
    backup_dir.mkdir(parents=True,exist_ok=True)
    label=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=backup_dir/f'registry-{label}.db'
    if out.exists():raise FileExistsError(out)
    with closing(sqlite3.connect(str(db_file))) as src,closing(sqlite3.connect(str(out))) as dst:
        src.backup(dst)
        check=dst.execute('PRAGMA integrity_check').fetchone()[0]
        if check!='ok':raise RuntimeError('SQLITE_BACKUP_INTEGRITY_FAILED')
    sha=hashlib.sha256(out.read_bytes()).hexdigest()
    manifest={'snapshot':out.name,'at_utc':label,'sha256':sha,'sqlite_integrity_check':check,
              'includes_oauth_tokens':False,'restoration':'MANUAL_ONLY'}
    (backup_dir/f'{out.name}.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default=str(Path(__file__).with_name('private')/'registry.db'))
    p.add_argument('--out',default=str(Path(__file__).with_name('private')/'backups'))
    a=p.parse_args();print(json.dumps(backup(Path(a.db),Path(a.out)),indent=2))
