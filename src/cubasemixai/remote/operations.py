"""Track-oriented Cubase operations exposed to Codex via MCP."""
import math

from .client import RemoteClient
from .workflow import RemoteWorkflow
from ..workflow import Workflow


def remote_batch_volume(delta_db: float, track_ids: list[str] | None = None) -> dict:
    """Prepare one relative dB change across selected channel unique IDs, or all non-output channels."""
    if not math.isfinite(delta_db) or not 0 < abs(delta_db) <= 24:
        raise ValueError("Use a nonzero relative change within 24 dB")
    plans = []
    with RemoteClient() as host:
        tracks = host.request("tracks", {})["tracks"]
        channels = [t for t in tracks if not t["unique_name"].startswith("OutputChannel")]
        if track_ids is not None:
            channels = [t for t in channels if t["unique_id"] in track_ids]
            if len(channels) != len(set(track_ids)):
                raise ValueError("Unknown, ambiguous, or output channel in selection")
        for channel in channels:
            p = host.request("channel_fader", {"target": channel})["parameter"]
            if p["unit"] != "dB" or not isinstance(p["plain"], (int, float)) or not math.isfinite(p["plain"]):
                raise ValueError(f"No finite dB fader value for {channel['title']}")
            args = dict(target=channel, object_id=channel["object_id"], parameter_tag=p["tag"],
                        value_kind="channel_db", unit="dB", after=p["plain"] + delta_db, max_delta=abs(delta_db))
            plan = host.request("preview", args)["plan"]
            if abs(plan["before"]["plain"] - p["plain"]) > .001:
                raise ValueError("Fader moved while preparing the batch")
            plans.append(plan)
    return RemoteWorkflow(Workflow()).propose_batch(plans, f"Non-master channel volume {delta_db:+g} dB")


def _slots(host, target):
    def children(object_id):
        return host.request("inspect", dict(target=target, object_id=object_id))["children"]
    racks = [c for c in children(target["object_id"]) if c["unique_name"] == "Inserts"]
    if len(racks) != 1:
        raise ValueError("Cannot identify the track insert rack")
    return children(racks[0]["object_id"])


def remote_find_insert(target: dict, name: str, vendor: str = "", slot_number: int | None = None) -> dict:
    """Find an installed effect (e.g. CLA, Waves) and propose it on the target track. Ambiguous names return choices."""
    if not name.strip():
        raise ValueError("Supply a plug-in name")
    with RemoteClient() as host:
        slots = _slots(host, target)
        if slot_number is not None:
            if not 1 <= slot_number <= len(slots):
                raise ValueError("Invalid 1-based slot number")
            slots = [slots[slot_number - 1]]
        for slot in slots:
            args = dict(target=target, object_id=slot["object_id"])
            page = host.request("plugins", args)
            if not page["loaded"]:
                break
        else:
            raise ValueError("No empty insert slot in selection")
        matches = {}
        while True:
            for entry in page["entries"]:
                if (name.strip().casefold() in (entry["name"] or "").casefold()
                    and vendor.strip().casefold() in (entry["vendor"] or "").casefold()):
                    matches[entry["uid"]] = entry
            if page["next_offset"] is None:
                break
            page = host.request("plugins", dict(args, offset=page["next_offset"]))
        exact = [m for m in matches.values() if m["name"].casefold() == name.strip().casefold()]
        candidates = exact or list(matches.values())
        if len(candidates) != 1:
            return {"matches": candidates, "proposal": None}
        plan = host.request("preview_plugin", dict(args, plugin_uid=candidates[0]["uid"]))["plan"]
    return RemoteWorkflow(Workflow())._store(plan, f"Insert {candidates[0]['name']} on {target['title']}")


def remote_map_insert(target: dict, slot_number: int) -> dict:
    """Read installed insert and all host-exposed parameter pages, with object IDs and tags for remote_propose."""
    with RemoteClient() as host:
        slots = _slots(host, target)
        if not 1 <= slot_number <= len(slots):
            raise ValueError("Invalid 1-based slot number")
        slot = slots[slot_number - 1]
        entries = host.request("inspect", dict(target=target, object_id=slot["object_id"]))["children"]
        mapped = []
        for obj in entries:
            mapped.append(_map_object(host, target, obj))
    return {"target": target, "slot": slot, "plugins": mapped}


def remote_audio_command(action: str) -> dict:
    """Render the current selection to audio in the project, open WAV export, or open Cubase's audio import dialog.
    For a full mix return, select WAV and Import into Project / Audio Track in the export dialog.
    Import places a chosen WAV using Cubase's current position and track selection.
    """
    if action not in {"render_selection", "export_mix", "import_audio"}:
        raise ValueError("Choose render_selection, export_mix, or import_audio")
    with RemoteClient() as host:
        return host.request("audio_command", {"action": action})

def _map_object(host, target, obj):
    parameters = []
    offset = 0
    while offset is not None:
        page = host.request("inspect", dict(target=target, object_id=obj["object_id"], parameter_offset=offset))
        if page["object"]["unique_id"] != obj["unique_id"]:
            raise ValueError("Insert changed while reading parameters")
        parameters.extend(page["parameters"])
        offset = page["next_offset"]
    return {"object": obj, "parameters": parameters}
