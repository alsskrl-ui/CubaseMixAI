from mcp.server.fastmcp import FastMCP
from .analysis import analyze, compare, analyze_stems
from .proposals import recommend
from .engine import integrate, propose_reference
from .evaluation import evaluate_render, compare_sections, export_ab, export_report
from .listening import clap_compare
from .backup import backup_project, verify_backup, restore_project
from .calibration import calibration_report
from .mastering import master_chain
from .render import create_render_job, finish_render_job
from .workflow import Workflow
from .remote.tools import remote_status, remote_tracks, remote_inspect, remote_plugins, remote_propose, remote_propose_plugin
from .midi_expression import add_midi_expression

server = FastMCP('CubaseMixAI')
for function in (analyze,compare,analyze_stems,recommend,integrate,propose_reference,evaluate_render,
                 compare_sections,export_ab,export_report,clap_compare,backup_project,verify_backup,
                 restore_project,calibration_report,master_chain,create_render_job,finish_render_job,
                 remote_status,remote_tracks,remote_inspect,remote_plugins,remote_propose,remote_propose_plugin,add_midi_expression):
    server.tool()(function)

@server.tool()
def propose(mapping_path: str, changes: list[dict], reason: str) -> dict:
    """Create a pending proposal. Approval requires the separate local review UI."""
    return Workflow().create(mapping_path,changes,reason)

@server.tool()
def apply(proposal_id: str, dry_run: bool = True) -> dict:
    """Preview or send a locally approved, unexpired, single-use proposal."""
    return Workflow().apply(proposal_id,dry_run=dry_run)

@server.tool()
def history() -> list[dict]:
    return Workflow().history()

@server.tool()
def restore(proposal_id: str) -> dict:
    """Create a reverse proposal requiring fresh local approval; no immediate MIDI."""
    return Workflow().restore_proposal(proposal_id)


def main():
    server.run(transport='stdio')
