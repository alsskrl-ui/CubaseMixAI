"""Persistent, single-use approval state machine. MIDI has no readback/rollback ACK."""
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from .control import load_mapping, validate_change, send_cc


class Workflow:
    def __init__(self, directory: str | None = None):
        self.root = Path(directory or os.environ.get("CUBASEMIXAI_STATE_DIR", ".cubasemixai")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "history.sqlite3"
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, created REAL, status TEXT, payload TEXT, error TEXT)")

    def connect(self):
        return sqlite3.connect(self.db, timeout=15)

    def create(self, mapping_path: str, changes: list[dict], reason: str, evidence: dict | None = None) -> dict:
        mapping, digest = load_mapping(mapping_path)
        if not changes or len(changes) > 32 or not reason.strip():
            raise ValueError("Need 1–32 changes and a reason")
        if len({c['control'] for c in changes}) != len(changes):
            raise ValueError("Duplicate control in proposal")
        clean = []
        for c in changes:
            validate_change(mapping, c)
            clean.append({"control": c["control"], "before": float(c["before"]), "after": float(c["after"]), "unit": c["unit"]})
        payload = {"mapping_path": str(Path(mapping_path).resolve()), "mapping_sha256": digest,
                   "changes": clean, "reason": reason,
                   "risk": "MIDI has no acknowledgement; current values are user-supplied. Back up Cubase before applying."}
        payload["evidence"] = evidence
        self._check_sources(payload)
        return self.store(payload)

    def store(self, payload: dict) -> dict:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        ident = uuid.uuid4().hex
        with self.connect() as con:
            con.execute("INSERT INTO proposals VALUES (?, ?, 'pending', ?, NULL)", (ident, time.time(), encoded))
        return self.get(ident)

    def _check_sources(self, payload):
        from .analysis import fingerprint
        for source in (payload.get("evidence") or {}).get("source_files", []):
            if fingerprint(source["path"]) != source["sha256"]:
                raise ValueError("Source WAV changed; create a new proposal")

    def get(self, ident: str) -> dict:
        with self.connect() as con:
            row = con.execute("SELECT * FROM proposals WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise ValueError("Proposal not found")
        return dict(id=row[0], created=row[1], status=row[2], payload=json.loads(row[3]), error=row[4])

    def history(self) -> list[dict]:
        with self.connect() as con:
            ids = [row[0] for row in con.execute("SELECT id FROM proposals ORDER BY created DESC LIMIT 100")]
        return [self.get(i) for i in ids]

    def decide(self, ident: str, approve: bool) -> dict:
        if self.get(ident)["payload"].get("backend") == "midi_remote":
            from .remote.workflow import RemoteWorkflow
            return RemoteWorkflow(self).decide(ident, approve)
        # Called only by the local review UI, never exposed as MCP tool.
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            p = self.get(ident)
            if p["status"] != "pending":
                raise ValueError("Proposal is not pending")
            if approve:
                if time.time()-p["created"] > 900:
                    raise ValueError("Proposal has expired (15 min)")
                self._check_sources(p["payload"])
                mapping, digest = load_mapping(p["payload"]["mapping_path"])
                if digest != p["payload"]["mapping_sha256"]:
                    raise ValueError("Mapping changed; create a new proposal")
                for c in p["payload"]["changes"]:
                    validate_change(mapping, c)
            con.execute("UPDATE proposals SET status=? WHERE id=?", ("approved" if approve else "rejected", ident))
        return self.get(ident)

    def apply(self, ident: str, *, dry_run: bool = True, sender=None) -> dict:
        p = self.get(ident)
        if p["payload"].get("backend") == "midi_remote":
            if sender is not None:
                raise ValueError("Legacy sender cannot bypass MIDI Remote host verification")
            from .remote.workflow import RemoteWorkflow
            return RemoteWorkflow(self).apply(ident, dry_run)
        self._check_sources(p["payload"])
        mapping, digest = load_mapping(p["payload"]["mapping_path"])
        if digest != p["payload"]["mapping_sha256"]:
            raise ValueError("Mapping changed; create a new proposal")
        messages = [validate_change(mapping, c) for c in p["payload"]["changes"]]
        if dry_run:
            return {"dry_run": True, "messages": messages, "sent": False}
        if mapping.get("simulation"):
            raise ValueError("Simulation mapping cannot send live MIDI")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            current = con.execute("SELECT status, created FROM proposals WHERE id=?", (ident,)).fetchone()
            if current[0] != "approved" or time.time()-current[1] > 900:
                raise ValueError("Live MIDI requires an unexpired, locally approved proposal")
            con.execute("UPDATE proposals SET status='sending' WHERE id=?", (ident,))
        # Persist the recovery snapshot before any external side effect.
        try:
            (self.root / f"{ident}.before.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
            (sender or send_cc)(mapping["port"], messages)
        except Exception as exc:
            with self.connect() as con:
                con.execute("UPDATE proposals SET status='uncertain', error=? WHERE id=?", (str(exc), ident))
            raise
        with self.connect() as con:
            con.execute("UPDATE proposals SET status='sent' WHERE id=?", (ident,))
        return {"sent": True, "acknowledged_by_cubase": False, "proposal": self.get(ident)}

    def restore_proposal(self, ident: str) -> dict:
        p = self.get(ident)
        if p["payload"].get("backend") == "midi_remote":
            from .remote.workflow import RemoteWorkflow
            return RemoteWorkflow(self).restore(ident)
        if p["status"] not in {"sent", "uncertain", "sending"}:
            raise ValueError("Only attempted live changes can be restored")
        changes = [{**c, "before": c["after"], "after": c["before"]} for c in p["payload"]["changes"]]
        return self.create(p["payload"]["mapping_path"], changes,
                           f"Restore snapshot for {ident}. Confirm actual Cubase values first; partial sends are possible.")
