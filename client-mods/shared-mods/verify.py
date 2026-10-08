"""Verify the combined package without launching Aion or loading its native DLL."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import prepare as shared

def verify(output):
    output=output.resolve();m=json.loads((output/'manifest.json').read_text());root=Path(m['originalClient']);target=Path(m['clientRoot'])
    assert m['mode']=='shared-mods' and m['mods']==shared.MODS
    origin,_=shared.origin_url(m['serverUrl'])
    for e in m['files']:
        assert shared.digest(output/e['path'])==e['installed'],e['path']
        assert (not (target/e['path']).exists()) if e['original'] is None else shared.digest(target/e['path'])==e['original'],e['path']
    for e in m['preservedFiles']:assert shared.digest(target/e['path'])==e['sha256'],e['path']
    sys.path.insert(0,str(shared.HERE.parent/'native-icon-bridge'));sys.path.insert(0,str(shared.HERE.parent/'market-shortcut'))
    dll,hooks,routes=shared.native_dll(root,origin)
    assert (output/'bin64/Game.dll').read_bytes()==dll and m['routes']==routes and hooks==m['hooks']['bin64/Game.dll']
    assert (output/'bin64/crysystem.dll').read_bytes()==shared.standalone.patch_plugin_key((root/'bin64/crysystem.dll').read_bytes())
    with shared.read_pak(output/'Plugin/RelicCalc/RelicCalc.pak') as archive:
        assert archive.testzip() is None
        lua=archive.read('PrivateMenus.lua').decode();toc=archive.read('RelicCalc.toc').decode()
        for route in routes:assert route in lua,route
        for command in ['/seasonpass','/centralmarket','/wardrobe','/journey']:assert command in lua
        for name in ['Warehouse.xml','Wardrobe.xml','Journey.xml']:
            assert name in toc;ET.fromstring(archive.read(name))
        assert 'PLAYER_ENTERING_WORLD' in lua and 'PrivateJourney_OnEvent' in lua
    for style in [1,2]:
        for relative,name in [(f'Data/ui/game_hud_s{style}/game_hud_s{style}.pak','start_dialog.xml'),('L10N/enu/Data/data.pak',f'ui/game_hud_s{style}/start_dialog.xml')]:
            with shared.read_pak(output/relative) as archive:
                tree=shared.binary_xml(archive.read(name));buttons=[tree.find(".//Widget[@name='"+widget+"']") for widget in ['central_market_button','season_pass_button']]
                assert all(b is not None for b in buttons)
                rects=[[float(v) for v in b.get('frame').split(',')] for b in buttons]
                assert rects[1][0]+rects[1][2]<=rects[0][0],'HUD icons overlap'
    inv=shared.inventory_modules()
    for relative,prefix in [('Data/ui/game/game.pak',''),('L10N/enu/Data/data.pak','ui/game/')]:
        with shared.read_pak(output/relative) as archive:
            for name in ['inventory_dialog.xml','inventory_dialog_new.xml']:
                tree=shared.binary_xml(archive.read(prefix+name))
                assert any(e.get('slot_num')=='279' for e in tree.iter()),name
            tree=shared.binary_xml(archive.read(prefix+'warehouse_dialog.xml'))
            assert {e.get('slot_num') for e in tree.iter()}.issuperset({'360','540'}),'Warehouse slot vectors'
    with shared.read_pak(output/'Data/Items/Items.pak') as archive:
        item=next(e for e in shared.binary_xml(archive.read('client_items_etc.xml')) if e.findtext('id')=='168100001')
        assert item.findtext('name')=='wardrobe_appearance_unlock'
    index=(output/'bin64/AionIconBridge.index').read_bytes();magic,count,textures,length,hashbytes=struct.unpack_from('<8sIIQ32s',index)
    assert magic==b'AICON002' and count>100000 and textures>3000
    assert length==(output/'Data/Items/Items.pak').stat().st_size and hashbytes.hex()==shared.digest(output/'Data/Items/Items.pak')
    assert 168100001 in [struct.unpack_from('<I',index,56+i*8)[0] for i in range(count)]
    assert origin.encode() in (output/'bin64/AionIconBridge.dll').read_bytes()
    bridge=(output/'bin64/AionIconBridge.dll').read_bytes()
    for value in ['AionWardrobeVisibility','AionWardrobeTick','WardrobePreview','JourneySession']:
        assert value.encode() in bridge or value.encode('utf-16le') in bridge,value
    assert '/seasonpass'.encode() in (output/'bin64/AionMarketShortcut.dll').read_bytes() and '/centralmarket'.encode() in (output/'bin64/AionMarketShortcut.dll').read_bytes()
    subprocess.run(['java',str(shared.HERE.parent/'season-pass/VerifySignatures.java'),str(output),str(root)],check=True)
    receipt=json.loads((output/'Aetherfall-mods.json').read_text());assert receipt['mods']==shared.MODS
    print('OK: five combined mods, four exact authenticated routes, collision-checked native hooks, separate HUD buttons, Inventory/Warehouse vectors, Wardrobe ticket/index and three addon signatures.')
if __name__=='__main__':verify(Path(sys.argv[1]))
