"""Build and actually install individual modules sequentially on a disposable client."""
import argparse
import importlib.util
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys
from manage import require_closed, MODS
from snapshot_client import FILES

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client-mods/shared-mods'))
import prepare as shared
spec = importlib.util.spec_from_file_location('cumulative_client_verify', ROOT / 'client-mods/shared-mods/verify.py')
checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)


def verify(original, output, first=None, resume=False):
    require_closed()
    if output.exists() and not resume: raise ValueError('Use a new disposable check directory')
    client = output / 'client'; recovery = output / 'recovery'
    for name in ([] if resume else FILES):
        path = client / name; path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / name, path)
    command = [shutil.which('pwsh') or 'powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File']
    def run(name, arguments, expected=True):
        result = subprocess.run(command + [str(ROOT / 'client-mods/season-pass' / name)] + arguments,
                                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if (result.returncode == 0) != expected: raise AssertionError(result.stdout + result.stderr)
        print(result.stdout.strip() if expected else 'OK: stale repeated install refused', flush=True)
    order = ['inventory-warehouse', 'wardrobe', 'journey', 'central-market', 'season-pass']
    for index, module in ([] if resume else enumerate(order, 1)):
        prepared = output / ('stage-' + str(index))
        if index == 1 and first:
            shutil.copytree(first, prepared)
            manifest = json.loads((prepared / 'manifest.json').read_bytes())
            manifest['clientRoot'] = str(client)
            (prepared / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        else: shared.prepare(client, prepared, 'https://play.example.com', original, [module])
        checker.verify(prepared)
        manifest = json.loads((prepared / 'manifest.json').read_bytes())
        assert set(manifest['mods']) == set(order[:index])
        run('install.ps1', ['-PreparedPath', str(prepared), '-BackupRoot', str(recovery)])
        for entry in manifest['files']: assert shared.digest(client / entry['path']) == entry['installed']
        run('install.ps1', ['-PreparedPath', str(prepared), '-BackupRoot', str(recovery)], expected=False)
        print('OK: sequential client step', index, manifest['mods'], flush=True)
    backups = sorted(recovery.iterdir())
    assert len(backups) == 5
    run('restore.ps1', ['-BackupPath', str(backups[0])], expected=False)
    for backup in reversed(backups): run('restore.ps1', ['-BackupPath', str(backup)])
    for name in FILES: assert shared.digest(client / name) == shared.digest(original / name), name
    for name in ('Aetherfall-mods.json', 'Addon.key', 'bin64/AionIconBridge.dll', 'bin64/AionMarketShortcut.dll'):
        assert not (client / name).exists(), name
    verify_native(original)
    print('OK: five real sequential installs, exact reverse restore, stale install/recovery rejection, all 31 native module subsets; no Aion execution.', flush=True)


def verify_native(original):
    # Every subset uses the same byte-level composition regardless of install order.
    combinations = 0
    for count in range(1, 6):
        for mods in itertools.combinations(MODS, count):
            dll, hooks, routes = shared.native_dll(original, 'https://play.example.com', mods)
            assert dll and hooks
            assert len(routes) == len(set(mods) - {'inventory-warehouse'})
            combinations += 1
    print('OK:', combinations, 'native module subsets; exact route counts and collision-checked hook composition; no native execution.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-client', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--first-package', type=Path)
    parser.add_argument('--resume-restore', action='store_true', help='Resume the completed five-step fixture at guarded recovery')
    parser.add_argument('--native-only', action='store_true')
    args = parser.parse_args()
    if args.native_only: verify_native(args.original_client)
    else: verify(args.original_client, args.output, args.first_package, args.resume_restore)
