from mcp.server.fastmcp import FastMCP
from .analysis import analyze, compare, analyze_stems
from .proposals import recommend
from .workflow import Workflow

server = FastMCP("CubaseMixAI")
server.tool()(analyze)
server.tool()(compare)
server.tool()(analyze_stems)
server.tool()(recommend)

@server.tool()
def propose(mapping_path: str, changes: list[dict], reason: str) -> dict:
    """Create a pending proposal. Approval requires the separate local review UI."""
    return Workflow().create(mapping_path, changes, reason)

@server.tool()
def apply(proposal_id: str, dry_run: bool = True) -> dict:
    """Preview or send a locally approved, unexpired, single-use proposal."""
    return Workflow().apply(proposal_id, dry_run=dry_run)

@server.tool()
def history() -> list[dict]:
    return Workflow().history()

@server.tool()
def restore(proposal_id: str) -> dict:
    """Create a reverse proposal requiring fresh local approval; no immediate MIDI."""
    return Workflow().restore_proposal(proposal_id)


def main():
    server.run(transport="stdio")
