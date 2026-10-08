"""Install or restore unified inventory and expanded warehouses. No third-party Python modules."""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
import uuid
import xml.etree.ElementTree as ET
import zipfile

from codec import read_pak, binary_xml, encode_pak, encode_binary_xml
from unified_inventory import patch_inventory_dll, patch_layout
from inventory_search import patch_search_dll
from warehouse_patch import patch_dll as patch_warehouse_dll, patch_archive as patch_warehouse_archive
from warehouse_search import patch_search_dll as patch_warehouse_search_dll
from detached_inventory import patch_detached_inventory

KIT = Path(__file__).resolve().parents[1]
SPEC = json.loads((KIT / 'manifest.json').read_text(encoding='utf-8'))
CLIENT_FILES = ['bin64/game.dll', 'Data/ui/game/game.pak', 'L10N/enu/data/data.pak']
SOURCE_FILES = SPEC['serverFiles']
INVENTORY_SOURCE_FILES = SPEC['inventoryServerFiles']
CONFIG = 'game-server/config/main/custom.properties'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rooted(root, relative):
    root = root.resolve()
    result = (root / relative).resolve()
    if root not in result.parents:
        raise ValueError('Path is outside the selected folder: ' + relative)
    return result


def ask_path(value, prompt):
    entered = (value if value is not None else input(prompt + '\n> ')).strip().strip('"')
    if not entered:
        raise ValueError('No folder entered. Copy the full folder path from File Explorer and run this installer again.')
    path = Path(entered).resolve()
    if not path.is_dir():
        raise ValueError('Folder does not exist: ' + str(path))
    return path


CLIENT_GUIDANCE = r'''CLIENT INSTALLATION - choose the Aion GAME folder
Open your installed Aion folder in File Explorer. It must contain:
  bin64\game.dll
  Data\ui\game\game.pak
  L10N\enu\data\data.pak
Example: if Game.dll is D:\Games\Aion 4.8 NA\bin64\game.dll,
enter D:\Games\Aion 4.8 NA
Do not enter bin64, Data, L10N, a launcher folder, or Inventory-Only.
Click File Explorer's address bar (Ctrl+L), copy the folder path,
then paste it below and press Enter. Example paths are not defaults.'''

SERVER_GUIDANCE = r'''SERVER SOURCE PATCH - choose the top-level SOURCE folder
Open your server source in File Explorer. It must contain:
  pom.xml
  game-server\src
  game-server\config\main\custom.properties
Example: if the source is D:\Servers\AionSource\game-server\src,
enter D:\Servers\AionSource
Do not enter game-server, src, target, a deployed server folder, or Inventory-Only.
Click File Explorer's address bar (Ctrl+L), copy the folder path,
then paste it below and press Enter. Example paths are not defaults.
This applies SOURCE changes only. Build and deploy your JAR afterward;
see README.md, Step 2. Players only need Install-Client.cmd.'''


def require_install_root(root, kind):
    """Explain a wrong destination before reading or changing installation files."""
    required = CLIENT_FILES if kind == 'client' else ['pom.xml'] + SOURCE_FILES + [CONFIG]
    missing = [name for name in required if not rooted(root, name).is_file()]
    if missing:
        guidance = CLIENT_GUIDANCE if kind == 'client' else SERVER_GUIDANCE
        raise ValueError('Wrong or incomplete ' + kind + ' folder: ' + str(root) +
                         '\nMissing required files:\n  ' + '\n  '.join(missing) +
                         '\n\n' + guidance + '\nNo files changed.')


def require_client_closed():
    if os.name != 'nt':
        raise ValueError('Client installation and restoration must run on Windows.')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                             "if (Get-Process -Name 'aion.bin' -ErrorAction SilentlyContinue) { exit 12 }; exit 0"],
                            capture_output=True, text=True)
    if result.returncode == 12:
        raise ValueError('Fully close Aion before installing or restoring the client.')
    if result.returncode:
        raise ValueError('Could not check whether Aion is closed. No files changed.')


def patch_archive(payload, prefix):
    """Rebuild two inventory XML entries; retain every other entry and its metadata."""
    with tempfile.TemporaryDirectory(prefix='inventory-read-') as temporary:
        source = Path(temporary) / 'source.pak'
        source.write_bytes(payload)
        with read_pak(source) as archive:
            infos = archive.infolist()
            if len({x.filename for x in infos}) != len(infos):
                raise ValueError('Duplicate archive entries are not supported.')
            content = {x.filename: archive.read(x.filename) for x in infos}
            comment = archive.comment
        changed = dict(content)
        for name in ['inventory_dialog.xml', 'inventory_dialog_new.xml']:
            name = prefix + name
            if name not in content:
                raise ValueError('The client is missing ' + name)
            tree = binary_xml(content[name])
            if tree.get('type') not in ('dlg_inventory', 'dlg_inventory_new'):
                raise ValueError('Unsupported inventory template: ' + name)
            result = patch_layout(tree)
            changed[name] = encode_binary_xml(result)
            if ET.tostring(binary_xml(changed[name])) != ET.tostring(result):
                raise ValueError('Inventory XML round-trip failed: ' + name)
        if prefix:
            strings = binary_xml(content['strings/stringtable_dialog.xml'])
            labels = {x.findtext('name'): x.findtext('body') for x in strings}
            if labels.get('STR_WHO_DIALOG__SEARCH') != 'Search' or labels.get('STR_PARTY_MATCH_DIALOG__SEARCH_CANCEL') != 'Clear':
                raise ValueError('This installer requires the English 4.8 NA string table.')
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w') as archive:
            archive.comment = comment
            for info in infos:
                archive.writestr(copy.copy(info), changed[info.filename])
        encoded = bytes(encode_pak(result.getvalue()))
        check_path = Path(temporary) / 'verified.pak'
        check_path.write_bytes(encoded)
        with read_pak(check_path) as check:
            if check.testzip() is not None or check.namelist() != list(content):
                raise ValueError('Rebuilt archive verification failed.')
            for name, value in changed.items():
                if check.read(name) != value:
                    raise ValueError('Archive verification failed: ' + name)
        allowed = {prefix + 'inventory_dialog.xml', prefix + 'inventory_dialog_new.xml'}
        if any(content[n] != changed[n] for n in content if n not in allowed):
            raise ValueError('An unrelated archive entry changed.')
        return encoded


def prepare_client(root):
    require_install_root(root, 'client')
    original = {p: rooted(root, p).read_bytes() for p in CLIENT_FILES}
    dll = original[CLIENT_FILES[0]]
    digest = sha(dll)
    if digest == SPEC['originalDllSha256']:
        dll = patch_search_dll(patch_inventory_dll(dll))
    elif digest not in (SPEC['inventoryDllSha256'], SPEC['inventoryWarehouseDllSha256'],
                        SPEC['inventoryWarehouseDetachedDllSha256']):
        raise ValueError('Game.dll is not the supported clean 4.8 NA, inventory-only or inventory/warehouse build. '
                         'Do not use your friend\'s modified Game.dll. Start with a clean matching client.')
    if sha(dll) == SPEC['inventoryDllSha256']:
        dll = patch_warehouse_search_dll(patch_warehouse_dll(dll))
    dll = patch_detached_inventory(dll)
    if sha(dll) != SPEC['inventoryWarehouseDetachedDllSha256']:
        raise ValueError('Inventory and warehouse DLL verification failed.')
    for p in CLIENT_FILES:
        if rooted(root, p + '.sig').exists():
            raise ValueError('A custom signature exists for ' + p + '. This installer supports the standard unsigned inventory files.')
    patched = {
        CLIENT_FILES[0]: dll,
        CLIENT_FILES[1]: patch_warehouse_archive(patch_archive(original[CLIENT_FILES[1]], ''), ''),
        CLIENT_FILES[2]: patch_warehouse_archive(patch_archive(original[CLIENT_FILES[2]], 'ui/game/'), 'ui/game/'),
    }
    return original, patched


def backup_files(root, originals, patched, kind):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    backup = root / 'Inventory-backups' / stamp if kind == 'client' else KIT / 'server' / 'backups' / stamp
    backup.mkdir(parents=True)
    entries = []
    for relative, data in originals.items():
        target = rooted(backup, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if sha(target.read_bytes()) != sha(data):
            raise ValueError('Backup verification failed: ' + relative)
        entries.append({'path': relative, 'original': sha(data), 'installed': sha(patched[relative])})
    manifest = {'kind': kind, 'root': str(root), 'files': entries}
    (backup / 'backup.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return backup


def atomic_write(path, data):
    temporary = path.with_name(path.name + '.inventory-' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(data)
        if sha(temporary.read_bytes()) != sha(data):
            raise ValueError('Temporary file verification failed: ' + str(path))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install_client(root):
    require_install_root(root, 'client')
    require_client_closed()
    original, patched = prepare_client(root)
    require_client_closed()
    for name, data in original.items():
        if rooted(root, name).read_bytes() != data:
            raise ValueError('Client changed during preparation: ' + name)
    backup = backup_files(root, original, patched, 'client')
    try:
        for name, data in patched.items():
            atomic_write(rooted(root, name), data)
            if sha(rooted(root, name).read_bytes()) != sha(data):
                raise ValueError('Installation verification failed: ' + name)
    except Exception:
        for name, data in original.items():
            atomic_write(rooted(root, name), data)
        raise
    print('Installed and verified three inventory and warehouse files. Backup:\n' + str(backup))
    print('Use the 64-bit client after installing and restarting the matching GameServer.')


def update_config(data):
    text = data.decode('utf-8-sig')
    newline = '\r\n' if '\r\n' in text else '\n'
    for key, value in [('gameserver.inventory.unified', 'true'), ('gameserver.cube.expansion_limit', '11'),
                       ('gameserver.warehouse.expanded', 'true')]:
        pattern = r'(?m)^[ \t]*' + re.escape(key) + r'[ \t]*=[^\r\n]*'
        matches = list(re.finditer(pattern, text))
        if len(matches) > 1:
            raise ValueError('Duplicate server setting: ' + key)
        if matches:
            text = re.sub(pattern, key + ' = ' + value, text)
        else:
            text = text.rstrip('\r\n') + newline + key + ' = ' + value + newline
    # Retain the original line endings and UTF-8 BOM if present.
    text = text.replace('\r\n', '\n').replace('\n', newline)
    return (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')


def git_apply(root, patch, check=False, reverse=False):
    git = shutil.which('git')
    if not git:
        raise ValueError('Git is required for the server source patch.')
    command = [git, '-C', str(root), 'apply', '--whitespace=nowarn']
    if check:
        command.append('--check')
    if reverse:
        command.append('--reverse')
    return subprocess.run(command + [str(patch)], capture_output=True, text=True)


def apply_server(root):
    require_install_root(root, 'server')
    before = {p: rooted(root, p).read_bytes() for p in SOURCE_FILES + [CONFIG]}
    # The old reference includes Solo RPG starting-tier changes absent upstream.
    # Keep its patch for existing installs; clean upstream needs no login/creation edits.
    customized = b'setWhNpcExpands(6)' in before[SOURCE_FILES[7]]
    inventory_patch = 'inventory-only.patch' if customized else 'inventory-upstream.patch'
    patches = [KIT / 'server' / name for name in (inventory_patch, 'warehouse-expansion.patch')]
    # Obtain the exact resulting files in an isolated source fixture before touching the real source.
    with tempfile.TemporaryDirectory(prefix='inventory-server-') as temporary:
        fixture = Path(temporary)
        for p, data in before.items():
            target = rooted(fixture, p)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Git's repository line-ending conversion is absent in this isolated folder.
            target.write_bytes(data.replace(b'\r\n', b'\n') if p in SOURCE_FILES else data)
        # Remove recognized changes in reverse order, then reapply both patches.
        # Their shared CustomConfig/Player contexts overlap, so checking the old
        # inventory patch directly against a fully expanded source is insufficient.
        for patch in reversed(patches):
            if git_apply(fixture, patch, check=True, reverse=True).returncode == 0:
                reversed_patch = git_apply(fixture, patch, reverse=True)
                if reversed_patch.returncode:
                    raise ValueError('Source patch validation failed: ' + reversed_patch.stderr)
        for patch in patches:
            checked = git_apply(fixture, patch, check=True)
            if checked.returncode:
                raise ValueError('The source differs from the supported server version. No files changed.\n'
                                 'Use the manual patch instructions in README.md.\n' + checked.stderr)
            applied = git_apply(fixture, patch)
            if applied.returncode:
                raise ValueError('Source patch validation failed: ' + applied.stderr)
        after = {p: rooted(fixture, p).read_bytes() for p in SOURCE_FILES}
        for p in SOURCE_FILES:
            if b'\r\n' in before[p]:
                after[p] = after[p].replace(b'\n', b'\r\n')
        after[CONFIG] = update_config(before[CONFIG])
    if before == after:
        print('The inventory and warehouse source patches and settings are already installed.')
        return
    for name, data in before.items():
        if rooted(root, name).read_bytes() != data:
            raise ValueError('Source changed during preparation: ' + name)
    backup = backup_files(root, before, after, 'server')
    try:
        for name, data in after.items():
            atomic_write(rooted(root, name), data)
    except Exception:
        for name, data in before.items():
            atomic_write(rooted(root, name), data)
        raise
    print('Applied inventory and warehouse changes to ten source files and three settings. Backup:\n' + str(backup))
    print('Build your GameServer, then stop it before replacing its JAR and updating its active config. See README.md.')


def restore(backup, expected_kind):
    record = json.loads((backup / 'backup.json').read_text(encoding='utf-8'))
    if record['kind'] != expected_kind:
        raise ValueError('This backup belongs to a different installer.')
    root = Path(record['root']).resolve()
    expected = set(CLIENT_FILES if expected_kind == 'client' else SOURCE_FILES + [CONFIG])
    entries = record['files']
    if expected_kind == 'server' and {e['path'] for e in entries} == set(INVENTORY_SOURCE_FILES + [CONFIG]):
        expected = set(INVENTORY_SOURCE_FILES + [CONFIG])
    if len(entries) != len(expected) or {e['path'] for e in entries} != expected:
        raise ValueError('Unexpected backup file list.')
    if expected_kind == 'client':
        require_client_closed()
    restored, current = {}, {}
    for entry in entries:
        name = entry['path']
        original = rooted(backup, name).read_bytes()
        active = rooted(root, name).read_bytes()
        if sha(original) != entry['original']:
            raise ValueError('Backup checksum failed: ' + name)
        if sha(active) not in (entry['installed'], entry['original']):
            raise ValueError('This file changed after installation; restore it manually to preserve your later edits: ' + name)
        restored[name], current[name] = original, active
    try:
        for name, data in restored.items():
            atomic_write(rooted(root, name), data)
    except Exception:
        for name, data in current.items():
            atomic_write(rooted(root, name), data)
        raise
    print('Restored and verified ' + str(len(restored)) + ' files in:\n' + str(root))
    if expected_kind == 'server':
        print('Rebuild and redeploy the server before starting it. See the rollback instructions.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install-client', 'prepare-client', 'apply-server', 'restore-client', 'restore-server'])
    parser.add_argument('--path', help='Client root, server source root, or backup folder')
    parser.add_argument('--output', help='Preparation output folder (prepare-client only)')
    args = parser.parse_args()
    if args.action.endswith('client') and not args.action.startswith('restore'):
        root = ask_path(args.path, CLIENT_GUIDANCE + '\n\nEnter the full Aion GAME folder path:')
        if args.action == 'install-client':
            install_client(root)
        else:
            if not args.output:
                raise ValueError('--output is required for preparation.')
            output = Path(args.output).resolve()
            if output == root or root in output.parents or output.exists():
                raise ValueError('Use a new output folder outside the client.')
            original, patched = prepare_client(root)
            output.mkdir(parents=True)
            for name, data in patched.items():
                destination = rooted(output, name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            print('Prepared three verified inventory and warehouse files. Client unchanged:\n' + str(output))
    elif args.action == 'apply-server':
        apply_server(ask_path(args.path, SERVER_GUIDANCE + '\n\nEnter the full server SOURCE folder path:'))
    else:
        restore(ask_path(args.path, 'Enter the backup folder containing backup.json:'), args.action.split('-')[1])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
