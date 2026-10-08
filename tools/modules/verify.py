"""Offline source composition, every install order, preservation and guarded restore."""
import argparse
import itertools
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
import manage


def verify(base, output):
    if output.exists(): raise ValueError('Use a new external check folder')
    output.mkdir(parents=True)
    tempfile.tempdir = str(output)
    root = output / 'source'
    spec, payload = manage.source_payload()
    for entry in spec['files']:
        source = base / entry['path']
        if source.is_file():
            target = root / entry['path']; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    before = {name: manage.read(root, name) for name in payload}
    unrelated = root / 'operator-notes.txt'; unrelated.write_bytes(b'keep unrelated source files')
    (root / manage.PROFILE_SOURCE).write_bytes(b'\xef\xbb\xbfoperator.setting = keep\r\n')
    original_profile = (root / manage.PROFILE_SOURCE).read_bytes()
    backups = []
    for module in reversed(manage.MODS):
        backup = manage.install_source(root, [module], output / 'recovery')
        assert backup is not None; backups.append(backup)
        record = manage.receipt(root, manage.SOURCE_RECEIPT)
        assert module in record['mods']
        assert unrelated.read_bytes() == b'keep unrelated source files'
        assert (root / manage.PROFILE_SOURCE).read_bytes().startswith(original_profile)
    assert manage.receipt(root, manage.SOURCE_RECEIPT)['mods'] == manage.MODS
    assert manage.install_source(root, ['wardrobe'], output / 'recovery') is None
    # A previous receipt cannot revert a later installation.
    try: manage.restore(backups[0]); raise AssertionError('Stale recovery accepted')
    except ValueError as error: assert 'Later modification' in str(error)
    for backup in reversed(backups): manage.restore(backup)
    assert {name: manage.read(root, name) for name in payload} == before
    assert (root / manage.PROFILE_SOURCE).read_bytes() == original_profile
    assert not (root / manage.SOURCE_RECEIPT).exists()
    # Refuse an overlapping custom method before any writes.
    relative = 'game-server/src/com/aionemu/gameserver/GameServer.java'
    (root / relative).write_bytes((root / relative).read_bytes().replace(b'initNioServer()', b'customNioServer()'))
    changed = {name: manage.read(root, name) for name in payload}
    try: manage.install_source(root, ['wardrobe'], output / 'recovery'); raise AssertionError('Conflicting source accepted')
    except ValueError as error: assert 'No files changed' in str(error)
    assert {name: manage.read(root, name) for name in payload} == changed
    # Use the same production planner with in-memory transactions for all 120 orders.
    baseline = dict(before); baseline[manage.PROFILE_SOURCE] = original_profile
    checks = 0
    for order in itertools.permutations(manage.MODS):
        state = dict(baseline)
        def read(_root, name): return state.get(name)
        def commit(_root, data, *_args, **_kwargs): state.update(data)
        with patch.object(manage, 'read', read), patch.object(manage, 'transaction', commit):
            for count, module in enumerate(order, 1):
                manage.install_source(root, [module], output / 'recovery')
                record = json.loads(state[manage.SOURCE_RECEIPT])
                assert set(record['mods']) == set(order[:count]); checks += 1
                expected = manage.profile(original_profile, record['mods'])
                assert set(state[manage.PROFILE_SOURCE].decode('utf-8-sig').splitlines()) == set(expected.decode('utf-8-sig').splitlines())
            assert json.loads(state[manage.SOURCE_RECEIPT])['mods'] == manage.MODS
    print('OK:', checks, 'source planner additions across 120 orders; actual sequential install/repeat/exact restore, custom setting preservation and conflict/stale recovery rejection.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); verify(args.source_root, args.output)
