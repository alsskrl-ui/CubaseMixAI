"""Read-only inspection and pending proposals for the modern backend."""
from .client import RemoteClient


def remote_status() -> dict:
    """Read actual driver identity, host version and feature flags."""
    with RemoteClient() as host:
        return host.hello


def remote_tracks() -> dict:
    """List mixer channels with session-scoped unique identities, not bank addresses."""
    with RemoteClient() as host:
        return host.request('tracks',{})


def remote_inspect(target: dict, object_id: int | None = None, parameter_offset: int = 0) -> dict:
    """Inspect a track or descendant object; enumerate physical units/parameters/children."""
    with RemoteClient() as host:
        return host.request('inspect',{'target':target,'object_id':object_id,'parameter_offset':parameter_offset})


def remote_plugins(target: dict, slot_id: int, offset: int = 0) -> dict:
    """Read the installed plugin catalog for a real insert slot (API 1.3 required)."""
    with RemoteClient() as host:
        return host.request('plugins',{'target':target,'object_id':slot_id,'offset':offset})


def remote_propose(target: dict, object_id: int, parameter_tag: int, after: float,
                   reason: str, value_kind: str = 'normalized', unit: str = '', max_delta: float = .1) -> dict:
    """Read current host value and prepare a pending change. No mutation or approval."""
    from .workflow import RemoteWorkflow
    from ..workflow import Workflow
    return RemoteWorkflow(Workflow()).propose(target,object_id,parameter_tag,after,reason,value_kind,unit,max_delta)


def remote_propose_plugin(target: dict, slot_id: int, plugin_uid: str, reason: str) -> dict:
    """Prepare an empty-slot plugin assignment; requires local UI approval; no replacement."""
    from .workflow import RemoteWorkflow
    from ..workflow import Workflow
    return RemoteWorkflow(Workflow()).propose_plugin(target,slot_id,plugin_uid,reason)
