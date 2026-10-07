"""Read-only verification of installed hashes and the ticket's actual English tooltip."""
import argparse
import json
from pathlib import Path
from prepare import sha,read_pak
from shortcut import binary_xml,TOOLTIP

def verify(package):
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8-sig'))
    root=Path(manifest['clientRoot'])
    for entry in manifest['files']:assert sha((root/entry['path']).read_bytes())==entry['installed'],entry['path']
    for entry in manifest['preservedFiles']:assert sha((root/entry['path']).read_bytes())==entry['sha256'],entry['path']
    archive=read_pak(root/'L10N/enu/Data/data.pak')
    strings=binary_xml(archive.read('strings/client_strings_ui.xml'))
    assert [e.findtext('body') for e in strings if e.findtext('name')==TOOLTIP]==['Aetherfall Season Pass']
    for style in (1,2):
        hud=binary_xml(archive.read(f'ui/game_hud_s{style}/start_dialog.xml'))
        ticket=hud.find("Widget[@name='season_pass_button']")
        assert ticket is not None and ticket.get('tooltip')==TOOLTIP
    print(f"OK: {len(manifest['files'])} installed files, all preserved files and actual English ticket tooltip in both HUDs: Aetherfall Season Pass.")

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('package',type=Path);args=parser.parse_args()
    try:verify(args.package)
    except Exception as e:print('FAIL:',e);raise SystemExit(1)
