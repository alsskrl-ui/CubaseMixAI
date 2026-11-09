import json
from pathlib import Path
import pytest
from cubasemixai.backup import backup_project,verify_backup,restore_project,MANIFEST


def test_backup_and_restore_hashes(tmp_path):
    source=tmp_path/'project';source.mkdir();(source/'test.cpr').write_bytes(b'project data')
    (source/'Audio').mkdir();(source/'Audio'/'stem.wav').write_bytes(b'audio bytes')
    backup=tmp_path/'backup';restore=tmp_path/'restore'
    assert backup_project(str(source),str(backup))['verified']
    assert verify_backup(str(backup))['files']==2
    assert restore_project(str(backup),str(restore))['overwritten'] is False
    assert (restore/'Audio'/'stem.wav').read_bytes()==b'audio bytes'
    with pytest.raises(ValueError): restore_project(str(backup),str(source))
    with pytest.raises(ValueError): backup_project(str(source),str(source/'nested'))
    (backup/'Audio'/'stem.wav').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='corrupted'): verify_backup(str(backup))
    with pytest.raises(ValueError): restore_project(str(backup),str(tmp_path/'new'))


def test_backup_rejects_symlink_and_traversal(tmp_path):
    source=tmp_path/'project';source.mkdir();(source/'test.cpr').write_text('data')
    link=source/'external'
    try: link.symlink_to(tmp_path/'outside')
    except OSError: pytest.skip('Symlinks require Windows privilege')
    with pytest.raises(ValueError,match='symlink'): backup_project(str(source),str(tmp_path/'backup'))
    link.unlink();backup=tmp_path/'backup';backup_project(str(source),str(backup))
    manifest=json.loads((backup/MANIFEST).read_text());manifest['files']['../outside']='bad'
    (backup/MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ValueError): verify_backup(str(backup))
    assert not (tmp_path/'restored').exists()
