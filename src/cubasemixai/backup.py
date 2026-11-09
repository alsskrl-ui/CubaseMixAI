"""Verifiable project-folder snapshots; restore always targets a new folder."""
import json
import os
import shutil
import stat
import uuid
from pathlib import Path
from .analysis import fingerprint

MANIFEST = 'cubasemixai-backup.json'


def _files(root: Path):
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(parent) / name
            reparse = getattr(p.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
            if p.is_symlink() or reparse:
                raise ValueError('Project backups reject symlinks/junctions; consolidate media first')
        for name in files:
            p = Path(parent) / name
            if getattr(p, 'is_junction', lambda: False)():
                raise ValueError('Junctions are not supported')
            yield p


def backup_project(project_dir: str, destination: str) -> dict:
    """Copy a saved, closed project folder, hash all files, publish after verification."""
    source, target = Path(project_dir).resolve(), Path(destination).resolve()
    if not source.is_dir() or not list(source.glob('*.cpr')):
        raise ValueError('Source must contain a Cubase .cpr project at its root')
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('Source and destination must be separate, non-nested folders')
    if target.exists():
        raise ValueError('Destination already exists; choose a new folder')
    files = list(_files(source))
    if (source / MANIFEST).exists():
        raise ValueError('Source contains a reserved backup manifest')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / (target.name + '.partial-' + uuid.uuid4().hex)
    temporary.mkdir()
    try:
        manifest = {'version': 1, 'source': str(source), 'files': {},
                    'limitation': 'Only files inside this folder are included. Consolidate external media with Cubase Back up Project first.'}
        for p in files:
            rel = p.relative_to(source)
            digest = fingerprint(str(p))
            out = temporary / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)
            if fingerprint(str(out)) != digest or fingerprint(str(p)) != digest:
                raise ValueError(f'Source changed during backup: {rel}; save and close Cubase')
            manifest['files'][rel.as_posix()] = digest
        if {p.relative_to(source).as_posix() for p in _files(source)} != set(manifest['files']):
            raise ValueError('Source file list changed during backup')
        for rel, digest in manifest['files'].items():
            if fingerprint(str(source / rel)) != digest:
                raise ValueError('Source changed during backup')
        (temporary / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        # mkdir guard prevents overwriting an existing/racing destination.
        target.mkdir()
        try:
            for child in temporary.iterdir():
                shutil.move(str(child), str(target / child.name))
        except Exception:
            raise ValueError('Backup publication interrupted; inspect destination before using it')
        temporary.rmdir()
        return {'backup': str(target), 'files': len(files), 'verified': True, 'limitation': manifest['limitation']}
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_backup(backup_dir: str) -> dict:
    root = Path(backup_dir).resolve()
    if (root / MANIFEST).is_symlink():
        raise ValueError('Manifest cannot be a symlink')
    manifest = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('version') != 1 or not manifest.get('files'):
        raise ValueError('Invalid backup manifest')
    actual = {p.relative_to(root).as_posix() for p in _files(root)} - {MANIFEST}
    if actual != set(manifest['files']):
        raise ValueError('Backup file list differs from manifest')
    for rel, digest in manifest['files'].items():
        p = root / rel
        if p.resolve().parent != root and root not in p.resolve().parents:
            raise ValueError('Unsafe manifest path')
        if not p.is_file() or fingerprint(str(p)) != digest:
            raise ValueError(f'Backup missing or corrupted: {rel}')
    return {'verified': True, 'files': len(actual), 'manifest': manifest}


def restore_project(backup_dir: str, destination: str) -> dict:
    source, target = Path(backup_dir).resolve(), Path(destination).resolve()
    verified = verify_backup(str(source))
    if target.exists() or source == target or source in target.parents or target in source.parents:
        raise ValueError('Restore needs a new, separate folder; no overwriting')
    target.mkdir(parents=True)
    try:
        for rel, digest in verified['manifest']['files'].items():
            out = target / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, out)
            if fingerprint(str(out)) != digest:
                raise ValueError(f'Restore checksum mismatch: {rel}')
    except Exception:
        # Keep partial copy for inspection, never touch the source backup.
        raise ValueError(f'Restore incomplete; inspect {target}')
    return {'restored': str(target), 'files': verified['files'], 'overwritten': False}
