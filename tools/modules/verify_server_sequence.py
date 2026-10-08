"""Install modules into an actual stock distribution without starting GameServer."""
import argparse
import json
from pathlib import Path
import manage


def verify(stock, cumulative, output, media):
    if output.exists(): raise ValueError('Use a new external runtime fixture folder')
    root = output / 'server'; root.mkdir(parents=True)
    base = manage.distribution(stock)
    for name, data in base.items(): manage.atomic(manage.path_at(root, name), data)
    operator = b'operator.example = preserve\n'
    manage.atomic(root / manage.PROFILE_SERVER, operator)
    notes = root / 'keep.txt'; notes.write_bytes(b'keep user files')
    before = {name: path.read_bytes() for name, path in ((p.relative_to(root).as_posix(), p) for p in root.rglob('*') if p.is_file())}
    backups = []
    for index, module in enumerate(['central-market', 'season-pass', 'wardrobe', 'journey', 'inventory-warehouse'], 1):
        backup = manage.install_server(root, cumulative, [module], output / 'recovery', stock if index == 1 else None, media)
        backups.append(backup)
        record = manage.receipt(root, manage.SERVER_RECEIPT)
        assert len(record['mods']) == index
        assert (root / manage.PROFILE_SERVER).read_bytes().startswith(operator)
        assert notes.read_bytes() == b'keep user files'
        assert (root / 'config/network/network.properties').read_bytes() == base['config/network/network.properties']
    assert manage.receipt(root, manage.SERVER_RECEIPT)['mods'] == manage.MODS
    assert manage.install_server(root, cumulative, ['wardrobe'], output / 'recovery', media=media) is None
    try: manage.restore(backups[0]); raise AssertionError('Stale server recovery accepted')
    except ValueError as error: assert 'Later modification' in str(error)
    for backup in reversed(backups): manage.restore(backup)
    after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert before == after, 'Server was not restored byte-exactly'
    # Reject a changed stock core before changing any other files.
    name = 'libs/game-server-4.8-SNAPSHOT.jar'
    (root / name).write_bytes((root / name).read_bytes() + b'custom')
    try: manage.install_server(root, cumulative, ['wardrobe'], output / 'recovery', stock); raise AssertionError('Unknown core accepted')
    except ValueError as error: assert 'No files changed' in str(error)
    # New-destination install uses the same code and correct single-module profile.
    new = output / 'new-server'
    manage.install_server(new, cumulative, ['wardrobe'], output / 'recovery')
    assert manage.receipt(new, manage.SERVER_RECEIPT)['mods'] == ['wardrobe']
    print('OK: actual stock-server sequential installs, repeat, settings preservation, exact reverse restore, unknown JAR/stale recovery rejection and fresh-folder install; no GameServer startup or SQL execution.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-archive', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--media', type=Path, required=True)
    args = parser.parse_args(); verify(args.stock_archive, args.archive, args.output, args.media)
