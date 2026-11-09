import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_tools():
    async def run():
        params = StdioServerParameters(command=sys.executable, args=['-c','from cubasemixai.mcp_server import main; main()'])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                names = {t.name for t in result.tools}
                assert {'analyze','compare','analyze_stems','recommend','propose','apply','history','restore','propose_reference','clap_compare','backup_project','finish_render_job'} <= names
                assert not {'approve','decide','send_cc'} & names
                assert len(names)==28
                assert {'remote_status','remote_tracks','remote_inspect','remote_plugins','remote_propose','remote_propose_plugin'} <= names
                # A rejected live request must never reach MIDI hardware.
                response = await session.call_tool('apply', {'proposal_id':'missing','dry_run':False})
                assert response.isError
    asyncio.run(run())
