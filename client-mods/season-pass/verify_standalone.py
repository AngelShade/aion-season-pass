"""Check the complete prepared client using hashes, native patch bytes, archive contents and RSA signatures."""
import json
import struct
import subprocess
import sys
from pathlib import Path
from standalone import sha, origin_url, native, patch_plugin_key, read_pak, binary_xml, HERE

def verify(output):
    output=output.resolve()
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8-sig'))
    root=Path(manifest['clientRoot'])
    assert manifest['feature']=='daeva-season-pass' and manifest['mode']=='standalone'
    origin,route=origin_url(manifest['serverUrl'])
    assert sha(root/'bin64/Game.dll')==native.ORIGINAL_SHA256
    assert sha(root/'Pub.key')==manifest['sourceKey']=='11c64ff8e5dde91b281b57ac2b372dc0c8f0df0df9e18c936335d10e63d85136'
    for entry in manifest['files']:
        assert sha(output/entry['path'])==entry['installed'],entry['path']
        if entry['original'] is None: assert not (root/entry['path']).exists(),entry['path']
        else: assert sha(root/entry['path'])==entry['original'],entry['path']
    for entry in manifest['preservedFiles']: assert sha(root/entry['path'])==entry['sha256'],entry['path']
    sys.path.insert(0,str(HERE.parent/'native-icon-bridge'))
    from patch_client import patch_dll
    sys.path.insert(0,str(HERE.parent/'market-shortcut'))
    from patch_binary import patch
    expected,hooks=patch(patch_dll(native.build_dll(root/'bin64/Game.dll',[],[route])))
    assert expected==(output/'bin64/Game.dll').read_bytes()
    assert hooks==manifest['hooks']['bin64/Game.dll']
    assert patch_plugin_key((root/'bin64/crysystem.dll').read_bytes())==(output/'bin64/crysystem.dll').read_bytes()
    with read_pak(output/'Plugin/RelicCalc/RelicCalc.pak') as archive:
        assert archive.testzip() is None
        lua=archive.read('PrivateMenus.lua').decode('utf-8')
        assert 'PRIVATE_SEASON_PASS_URL = '+json.dumps(route) in lua and '/seasonpass' in lua
        assert 'season_ticket_up' in lua
        assert 'Warehouse.xml' in archive.read('RelicCalc.toc').decode('utf-8')
        tree=binary_xml(archive.read('Warehouse.xml')) if archive.read('Warehouse.xml')[:2]!=b'\xff\xfe' else __import__('xml.etree.ElementTree',fromlist=['fromstring']).fromstring(archive.read('Warehouse.xml'))
        assert tree.find(".//Widget[@name='PrivateWarehouseBrowser']") is not None
    for style in (1,2):
        with read_pak(output/f'Data/ui/game_hud_s{style}/game_hud_s{style}.pak') as archive:
            tree=binary_xml(archive.read('start_dialog.xml'))
            button=tree.find(".//Widget[@name='season_pass_button']")
            assert button is not None and button.get('preset')=='season_ticket_button'
        with read_pak(output/'L10N/enu/Data/data.pak') as archive:
            assert binary_xml(archive.read(f'ui/game_hud_s{style}/start_dialog.xml')).find(".//Widget[@name='season_pass_button']") is not None
    with read_pak(output/'Data/ui/ui.pak') as archive: assert binary_xml(archive.read('UI_Preload.xml')).find(".//Skin[@name='season_ticket_up']") is not None
    index=(output/'bin64/AionIconBridge.index').read_bytes()
    magic,items,textures,length,digest=struct.unpack_from('<8sIIQ32s',index)
    assert magic==b'AICON002' and items>40000 and textures>3000 and length==(root/'Data/Items/Items.pak').stat().st_size
    assert digest.hex()==sha(root/'Data/Items/Items.pak')
    assert manifest['nativeIcons']['origin']==origin
    assert origin.encode('ascii') in (output/'bin64/AionIconBridge.dll').read_bytes()
    subprocess.run(['java',str(HERE/'VerifySignatures.java'),str(output),str(root)],check=True)
    print('OK: standalone native browser/authentication, configured origin, native icon index, English ticket/HUDs, stock model key and all signatures.')

if __name__=='__main__':
    verify(Path(sys.argv[1]))
