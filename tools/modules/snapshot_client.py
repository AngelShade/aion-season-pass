"""Save the original inputs needed to compose subsequent client module installs."""
import json
from pathlib import Path
import shutil
import sys
from manage import require_closed, sha, encoded

FILES = ['bin64/Game.dll', 'bin64/crysystem.dll', 'bin64/Awesomium.dll', 'Pub.key',
         'bin32/bin32.pak', 'bin32/bin32.pak.sig', 'Data/func_pet/func_pet.pak',
         'Data/func_pet/func_pet.pak.sig', 'Data/Items/Items.pak',
         'Plugin/RelicCalc/RelicCalc.pak', 'Plugin/RelicCalc/RelicCalc.pak.sig', 'Data/ui/ui.pak', 'Textures/ui/ui.pak',
         'L10N/enu/Data/data.pak', 'Data/ui/game/game.pak',
         'Data/ui/game_hud_s1/game_hud_s1.pak', 'Data/ui/game_hud_s2/game_hud_s2.pak',
         'Textures/loading/loading_lf1.dds', 'Textures/loading/loading_lc1.dds',
         'Textures/loading/loading_df1.dds', 'Textures/loading/loading_dc1.dds']


def snapshot(root, output):
    root, output = root.resolve(), output.resolve()
    if output.exists() or root == output or root in output.parents or output in root.parents:
        raise ValueError('Use a new external original-input folder')
    require_closed()
    if sha((root / 'bin64/Game.dll').read_bytes()) != '5334cf2164468678e45fe1a5decf58a0fbc4fd7f22cfdcbb87d28edce8d2c11c':
        raise ValueError('An existing standalone mod needs a separate supported original client: -OriginalClient')
    records = []
    for name in FILES:
        source = root / name
        if not source.is_file(): raise ValueError('Missing original client input: ' + name)
        records.append(dict(path=name, sha256=sha(source.read_bytes())))
    for entry in records:
        source, target = root / entry['path'], output / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha(source.read_bytes()) != entry['sha256'] or sha(target.read_bytes()) != entry['sha256']:
            raise ValueError('Client changed while saving original inputs')
    (output / 'original-inputs.json').write_bytes(encoded(dict(version=1, files=records)))
    print('OK: original inputs preserved externally:', output)


if __name__ == '__main__': snapshot(Path(sys.argv[1]), Path(sys.argv[2]))
