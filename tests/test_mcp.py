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
                assert names == {'analyze','compare','analyze_stems','recommend','propose','apply','history','restore'}
                # A rejected live request must never reach MIDI hardware.
                response = await session.call_tool('apply', {'proposal_id':'missing','dry_run':False})
                assert response.isError
    asyncio.run(run())
