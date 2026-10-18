"""Fixed ANTI-01 adapter entry point. Logical identity, not OS isolation."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_mcp import main

if __name__ == '__main__':
    if not os.environ.get('APPDATA'):
        raise SystemExit('APPDATA required')
    main(['--identity','ANTI-01','--token-file',str(Path(os.environ['APPDATA'])/'KTOOLMCP/identities/ANTI-01/client_token.txt')])
