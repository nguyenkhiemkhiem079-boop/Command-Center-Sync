"""Read-only MCP discovery/invocation. No provider session or heartbeat implied."""
import argparse,asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def run(args):
    env=dict(os.environ,KTOOL_COORDINATOR_PORT=str(args.port))
    adapter=Path(__file__).resolve().parents[1]/'client_mcp.py'
    params=StdioServerParameters(command=sys.executable,args=[str(adapter),'--identity',args.identity,'--token-file',args.token_file],env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize();names=[t.name for t in (await session.list_tools()).tools];calls={}
            queries=[('status',{}),('governance_identity',{}),('delivery_outbox',{})]
            if args.mission:queries.append(('mission_result',{'mission':args.mission}))
            for name,body in queries:
                result=await session.call_tool(name,body);data=json.loads(result.content[0].text)
                if result.isError or not data.get('ok'):raise RuntimeError('MCP_PROBE_FAILED_'+name)
                calls[name]={'status':'PASS','response_kind':type(data['result']).__name__}
            return {'scope':'REAL_STDIO_NOT_ANTIGRAVITY','identity':args.identity,'tool_count':len(names),'tools':names,'calls':calls,'provider_session':'NOT_EXECUTED'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--identity',choices=('CODEX','ANTI-01','ANTI-02'),required=True);p.add_argument('--token-file',required=True);p.add_argument('--port',type=int,default=8876);p.add_argument('--mission');a=p.parse_args();print(json.dumps(asyncio.run(run(a)),indent=2))
