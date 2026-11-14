"""Send an existing WAV to Cubase 15's native Windows audio import dialog."""
import os
import time
from pathlib import Path

import soundfile


def remote_import_wav(path: str) -> dict:
    """Import a WAV at Cubase's current cursor. Any conversion/options dialog remains in Cubase."""
    from .operations import remote_audio_command

    if os.name != "nt":
        raise ValueError("File selection currently requires Windows")
    wav = Path(path).resolve(strict=True)
    if wav.suffix.lower() != ".wav" or soundfile.info(wav).format not in {"WAV", "WAVEX", "RF64"}:
        raise ValueError("Choose a WAV audio file")
    import win32api
    import win32con
    import win32gui
    import win32process

    def cubase_dialogs():
        dialogs = {}
        def visit(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == "#32770":
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    with win32api.OpenProcess(0x410, False, pid) as proc:
                        exe = win32process.GetModuleFileNameEx(proc, 0)
                except OSError:
                    return
                if Path(exe).name.lower() == "cubase15.exe":
                    dialogs[hwnd] = pid
        win32gui.EnumWindows(visit, None)
        return dialogs

    existing = cubase_dialogs()
    if existing:
        raise ValueError("Close the existing Cubase dialog before importing")
    remote_audio_command("import_audio")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        for hwnd in cubase_dialogs():
            title = win32gui.GetWindowText(hwnd).casefold()
            if not any(word in title for word in ("import", "open", "가져오기", "열기")):
                continue
            edits = []
            def find_filename(child, _):
                if win32gui.GetClassName(child) != "Edit":
                    return
                parent = child
                while parent and parent != hwnd:
                    if win32gui.GetDlgCtrlID(parent) in (1148, 1152):
                        edits.append(child)
                        break
                    parent = win32gui.GetParent(parent)
            win32gui.EnumChildWindows(hwnd, find_filename, None)
            if len(edits) != 1 or not win32gui.GetDlgItem(hwnd, win32con.IDOK):
                continue
            win32gui.SendMessage(edits[0], win32con.WM_SETTEXT, 0, str(wav))
            if win32gui.GetWindowText(edits[0]) != str(wav):
                raise ValueError("Cubase did not accept the WAV path")
            win32gui.PostMessage(hwnd, win32con.WM_COMMAND, win32con.IDOK, 0)
            return {"status": "file_submitted", "path": str(wav),
                    "next": "Confirm import options if shown; check the event at the project cursor."}
        time.sleep(.15)
    return {"status": "awaiting_file_selection", "path": str(wav),
            "next": "Select this WAV in the Cubase import dialog."}

def remote_rerender_mix(before: str, reference: str, output: str) -> dict:
    """Start a tracked re-render. Confirm locators and the returned output path in Cubase's export dialog.
    For native round-trip, choose After Export / Create Audio Track (or import the finished WAV separately).
    """
    from .operations import remote_audio_command
    from ..render import create_render_job

    job = create_render_job(before, reference, output)
    try:
        command = remote_audio_command("export_mix")
    except (ValueError, OSError) as exc:
        return {"job": job, "status": "export_not_confirmed", "error": str(exc)}
    return {"job": job, "command": command, "status": "awaiting_native_export",
            "next": "Export WAV to job.output, then call finish_render_job. Use remote_import_wav for a separate processed WAV."}
