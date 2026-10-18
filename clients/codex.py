"""Fixed CODEX adapter entry point. Credential contents never appear in arguments."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_mcp import main

if __name__ == '__main__':
    if not os.environ.get('APPDATA'):
        raise SystemExit('APPDATA required')
    main(['--identity','CODEX','--token-file',str(Path(os.environ['APPDATA'])/'KTOOLMCP/identities/CODEX/client_token.txt')])
