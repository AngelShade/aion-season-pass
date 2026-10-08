"""Cumulative source/runtime module installation with external, guarded recovery."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MODS = ['season-pass', 'central-market', 'wardrobe', 'journey', 'inventory-warehouse']
SOURCE_RECEIPT = 'Aetherfall-source-mods.json'
SERVER_RECEIPT = 'Aetherfall-server-mods.json'
PROFILE_SOURCE = 'game-server/config/mygs.properties'
PROFILE_SERVER = 'config/mygs.properties'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(data):
    return data.replace(b'\r\n', b'\n')


def path_at(root, relative):
    parts = PurePosixPath(relative).parts
    if not parts or '..' in parts or '\\' in relative or ':' in relative or relative.startswith('/'):
        raise ValueError('Invalid package path: ' + relative)
    target = (root / relative).resolve()
    if root.resolve() not in target.parents:
        raise ValueError('Path outside selected folder: ' + relative)
    return target


def read(root, relative):
    path = path_at(root, relative)
    return path.read_bytes() if path.is_file() else None


def encoded(record):
    return (json.dumps(record, indent=2) + '\n').encode('utf-8')


def selection(previous, added):
    chosen = set(previous) | set(added)
    if not chosen or not chosen.issubset(MODS):
        raise ValueError('Unsupported module selection')
    return [name for name in MODS if name in chosen]


def profile(data, mods):
    data = data or b''
    text = data.decode('utf-8-sig')
    newline = '\r\n' if '\r\n' in text else '\n'
    values = {
        'gameserver.sharedmods.enable': True,
        'gameserver.sharedmods.market': 'central-market' in mods,
        'gameserver.sharedmods.wardrobe': 'wardrobe' in mods,
        'gameserver.sharedmods.pass': 'season-pass' in mods,
        'gameserver.inventory.unified': 'inventory-warehouse' in mods,
        'gameserver.warehouse.expanded': 'inventory-warehouse' in mods,
        'gameserver.poeta.journey.enable': 'journey' in mods,
    }
    if 'inventory-warehouse' in mods: values['gameserver.cube.expansion_limit'] = 11
    if 'journey' in mods: values['gameserver.simple.secondclass.enable'] = False
    for key, value in values.items():
        pattern = r'(?m)^[ \t]*' + re.escape(key) + r'[ \t]*=[^\r\n]*'
        if len(re.findall(pattern, text)) > 1:
            raise ValueError('Duplicate setting: ' + key)
        line = key + ' = ' + (str(value).lower() if isinstance(value, bool) else str(value))
        if re.search(pattern, text): text = re.sub(pattern, lambda _: line, text)
        else: text = text.rstrip('\r\n') + newline + line + newline
    return (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')


def require_closed():
    """Inspect processes; failure to inspect is not evidence of shutdown."""
    if os.name != 'nt': raise ValueError('Runtime installation requires Windows process inspection')
    command = r"""$ErrorActionPreference='Stop'; try {
      $p=@(Get-CimInstance Win32_Process);
      if($p | Where-Object { $_.Name -match '^java(w)?\.exe$' -and -not $_.CommandLine }) { exit 13 }
      if($p | Where-Object { $_.Name -match '^(aion(\.bin|\.exe)?|GameServer\.exe)$' -or
        ($_.Name -match '^java(w)?\.exe$' -and $_.CommandLine -match 'com\.aionemu\.gameserver\.GameServer') }) { exit 12 }
      exit 0
    } catch { exit 13 }"""
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True)
    if result.returncode: raise ValueError('Close GameServer and Aion; process inspection must succeed. No installation performed.')


def atomic(path, data):
    if data is None:
        if path.exists(): path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.module-' + uuid.uuid4().hex)
    try:
        temporary.write_bytes(data)
        if temporary.read_bytes() != data: raise ValueError('Temporary file verification failed')
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def transaction(root, payload, backups, kind, inspect=False):
    root, backups = root.resolve(), backups.resolve()
    if root == backups or root in backups.parents or backups in root.parents:
        raise ValueError('Recovery directory must be outside the target')
    if inspect: require_closed()
    before = {name: read(root, name) for name in payload}
    payload = {name: data for name, data in payload.items() if data != before[name]}
    before = {name: before[name] for name in payload}
    if not payload:
        print('OK: module selection already installed'); return None
    backup = backups / (datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '-' + kind)
    backup.mkdir(parents=True)
    entries = []
    for name, data in before.items():
        if data is not None: atomic(path_at(backup, name), data)
        entries.append(dict(path=name, original=sha(data) if data is not None else None,
                            installed=sha(payload[name]) if payload[name] is not None else None))
    record = dict(version=1, kind=kind, root=str(root), files=entries)
    (backup / 'recovery.json').write_bytes(encoded(record))
    if inspect: require_closed()
    if any(read(root, name) != data for name, data in before.items()):
        raise ValueError('Target changed during preparation; no files changed')
    try:
        # Receipt commits last; the stopped server cannot observe an intermediate state.
        for name in sorted(payload, key=lambda p: p.endswith('-mods.json')):
            atomic(path_at(root, name), payload[name])
            if read(root, name) != payload[name]: raise ValueError('Installed verification failed: ' + name)
    except Exception:
        for name, data in before.items(): atomic(path_at(root, name), data)
        raise
    print('OK: installed modules; guarded recovery:', backup)
    return backup


def restore(backup):
    record = json.loads((backup / 'recovery.json').read_bytes())
    root = Path(record['root']).resolve()
    if record['kind'] == 'server': require_closed()
    payload = {}
    names = set()
    for entry in record['files']:
        name = entry['path']
        if name in names: raise ValueError('Duplicate recovery path')
        names.add(name)
        current = read(root, name)
        if (sha(current) if current is not None else None) != entry['installed']:
            raise ValueError('Later modification would be lost; restore later module transactions first: ' + name)
        saved = read(backup, name) if entry['original'] is not None else None
        if (sha(saved) if saved is not None else None) != entry['original']:
            raise ValueError('Recovery content changed: ' + name)
        payload[name] = saved
    transaction(root, payload, backup.parent, record['kind'], inspect=record['kind'] == 'server')
    print('OK: restored exact prior files and module selection')


def receipt(root, name):
    data = read(root, name)
    if data is None: return None
    result = json.loads(data)
    if result.get('version') != 1 or result.get('kind') not in ('source', 'server'):
        raise ValueError('Unsupported module receipt')
    selection(result['mods'], [])
    return result


def source_payload():
    spec = json.loads((ROOT / 'tools/modules/source-baseline.json').read_bytes())
    payload = {e['path']: (ROOT / e['path']).read_bytes() for e in spec['files']}
    for entry in spec['files']:
        if sha(normalized(payload[entry['path']])) != entry['payload']:
            raise ValueError('Integration source differs from its release manifest: ' + entry['path'])
    return spec, payload


def merge_payload(root, payload, prior, baseline):
    managed = prior['managed'] if prior else {}
    for name, data in list(payload.items()):
        current = read(root, name)
        if current == data or (current is not None and normalized(current) == normalized(data)):
            payload[name] = current; continue
        # Operator-edited defaults stay intact when this release has not changed them.
        if prior and name.startswith(('config/', 'game-server/config/')) and managed.get(name) == sha(data):
            payload[name] = current; continue
        expected = managed.get(name) if prior else baseline.get(name)
        actual = sha(current) if current is not None else None
        normalized_actual = sha(normalized(current)) if current is not None else None
        if actual != expected and (prior or normalized_actual != expected):
            raise ValueError('Unrecognized change would be overwritten: ' + name + '. No files changed.')
        if current is not None and b'\r\n' in current and name.endswith(('.java', '.xml', '.properties', '.sql')):
            payload[name] = normalized(data).replace(b'\n', b'\r\n')
    return payload


def install_source(root, added, backups):
    if not (root / 'pom.xml').is_file() or not (root / 'game-server/src').is_dir():
        raise ValueError('Choose the top-level Beyond Aion source checkout')
    prior = receipt(root, SOURCE_RECEIPT)
    mods = selection(prior['mods'] if prior else [], added)
    spec, payload = source_payload()
    baseline = {e['path']: e['original'] for e in spec['files']}
    payload = merge_payload(root, payload, prior, baseline)
    payload[PROFILE_SOURCE] = profile(read(root, PROFILE_SOURCE), mods)
    record = dict(version=1, kind='source', upstream=spec['upstream'], mods=mods,
                  managed={name: sha(data) for name, data in payload.items() if name != PROFILE_SOURCE})
    payload[SOURCE_RECEIPT] = encoded(record)
    return transaction(root, payload, backups, 'source')


def distribution(archive):
    checksum = Path(str(archive) + '.sha256').read_text().split()[0]
    if not re.fullmatch('[0-9a-fA-F]{64}', checksum) or sha(archive.read_bytes()) != checksum.lower():
        raise ValueError('Distribution checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        candidates = [n for n in z.namelist() if n.endswith('/libs/game-server-4.8-SNAPSHOT.jar')]
        if len(candidates) != 1: raise ValueError('Unsupported server distribution')
        prefix = candidates[0][:-len('libs/game-server-4.8-SNAPSHOT.jar')]
        files = {}
        for info in z.infolist():
            if not info.filename.startswith(prefix): raise ValueError('Mixed archive roots')
            name = info.filename[len(prefix):]
            if info.is_dir() or not name: continue
            path_at(Path.cwd(), name)
            if name in files: raise ValueError('Duplicate distribution path')
            files[name] = z.read(info)
        return files


def install_server(root, archive, added, backups, baseline_archive=None, media=None):
    stamp = json.loads(Path(str(archive) + '.modules.json').read_bytes())
    if stamp.get('version') != 1 or stamp.get('archiveSha256') != sha(archive.read_bytes()) or stamp.get('sourceManifestSha256') != sha((ROOT / 'tools/modules/source-baseline.json').read_bytes()):
        raise ValueError('Server archive is from a different integration release. Build it with this release\'s Build-Server.ps1.')
    incoming = distribution(archive)
    for name in ('config/season-pass/schema.sql', 'config/wardrobe/schema.sql',
                 'config/central-market/schema.sql', 'config/journey/schema.sql'):
        if name not in incoming: raise ValueError('Archive is missing shared module dependencies: ' + name)
    prior = receipt(root, SERVER_RECEIPT)
    mods = selection(prior['mods'] if prior else [], added)
    new = not root.exists() or not any(root.iterdir())
    if new:
        payload, baseline = incoming, {}
    else:
        if not prior and baseline_archive is None:
            raise ValueError('First install into an existing stock server requires its matching clean distribution --baseline-archive')
        baseline_files = distribution(baseline_archive) if not prior else {}
        spec, _ = source_payload()
        names = {e['path'][len('game-server/'):] for e in spec['files']
                 if e['path'].startswith(('game-server/config/', 'game-server/data/', 'game-server/sql/'))}
        names.update(name for name in incoming if name.startswith('libs/'))
        # Include every new mod dependency; do not replace unrelated defaults or launchers.
        names.update(name for name in incoming if name.startswith(('config/central-market/', 'config/wardrobe/', 'config/season-pass/', 'config/journey/')))
        payload = {name: incoming[name] for name in names if name in incoming}
        baseline = {name: sha(baseline_files[name]) if name in baseline_files else None for name in payload}
        payload = merge_payload(root, payload, prior, baseline)
    payload[PROFILE_SERVER] = profile(read(root, PROFILE_SERVER), mods)
    if 'journey' in mods:
        for name in ('poeta.jpg', 'sanctum.jpg', 'ishalgen.jpg', 'pandaemonium.jpg'):
            relative = 'config/journey/media/' + name
            if read(root, relative) is None:
                if media is None or not (media / name).is_file():
                    raise ValueError('Journey requires locally generated client artwork: --media directory')
                payload[relative] = (media / name).read_bytes()
    managed = dict(prior['managed']) if prior else {}
    managed.update({name: sha(data) for name, data in payload.items() if name != PROFILE_SERVER})
    payload[SERVER_RECEIPT] = encoded(dict(version=1, kind='server', mods=mods, managed=managed))
    return transaction(root, payload, backups, 'server', inspect=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['source', 'server', 'restore', 'check'])
    parser.add_argument('--path', type=Path, required=True)
    parser.add_argument('--module', choices=MODS, action='append')
    parser.add_argument('--backups', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--baseline-archive', type=Path)
    parser.add_argument('--media', type=Path)
    args = parser.parse_args()
    if args.action == 'check': require_closed(); print('OK: process inspection passed'); return
    if args.action == 'restore': restore(args.path); return
    if not args.module or not args.backups: parser.error('--module and --backups are required')
    if args.action == 'source': install_source(args.path, args.module, args.backups)
    else:
        if not args.archive: parser.error('--archive is required')
        install_server(args.path, args.archive, args.module, args.backups, args.baseline_archive, args.media)


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit('ERROR: ' + str(error))
