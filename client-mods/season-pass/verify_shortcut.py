"""Verify the native ticket resources and preserve all unrelated installed artwork/layouts."""
from pathlib import Path
import io
import xml.etree.ElementTree as ET
from PIL import Image
import shortcut
from artwork import read_pak,binary_xml

def unchanged(before,after,label):
    assert ET.tostring(before)==ET.tostring(after),'Unrelated XML changed: '+label

def verify(root,out):
    expected={
      'Data/ui/ui.pak':{'UI_Preload.xml'},
      'Textures/ui/ui.pak':{'season_ticket.dds'},
      'L10N/enu/Data/data.pak':{'ui/ui_preload.xml','strings/client_strings_ui.xml','ui/game_hud_s1/start_dialog.xml','ui/game_hud_s2/start_dialog.xml'},
      'Data/ui/game_hud_s1/game_hud_s1.pak':{'start_dialog.xml'},
      'Data/ui/game_hud_s2/game_hud_s2.pak':{'start_dialog.xml'}}
    for rel,allowed in expected.items():
        old=read_pak(root/rel);new=read_pak(out/rel)
        assert new.testzip() is None
        assert set(new.namelist())-set(old.namelist())==(allowed if rel.startswith('Textures') else set())
        assert not set(old.namelist())-set(new.namelist())
        for entry in new.namelist():
            if entry not in allowed:assert old.read(entry)==new.read(entry),(rel,entry)
            elif entry.endswith('start_dialog.xml'):
                before=binary_xml(old.read(entry));after=binary_xml(new.read(entry))
                ticket=after.find("Widget[@name='season_pass_button']");market=after.find("Widget[@name='central_market_button']")
                assert ticket is not None and ticket.get('preset')=='season_ticket_button' and ticket.get('tooltip')==shortcut.TOOLTIP
                x,y,w,h=map(int,ticket.get('frame').split(','));mx,my,mw,mh=map(int,market.get('frame').split(','))
                assert (x,y,w,h)==(mx,my-34,34,32) and y>=0 and y+h+2==my
                after.remove(ticket);unchanged(before,after,rel+'/'+entry)
            elif entry.lower().endswith('ui_preload.xml'):
                before=binary_xml(old.read(entry));after=binary_xml(new.read(entry))
                names=set()
                for parent in after.iter():
                    for child in list(parent):
                        if child.get('name','').startswith('season_ticket'):
                            names.add(child.get('name'))
                            if child.tag=='Skin':
                                assert child.get('texture')=='Textures/UI/season_ticket'
                                assert child.get('src_image') in ['0,0,34,32','40,0,34,32','80,0,34,32']
                            else:assert child.tag=='Preset' and [(s.get('sub_state'),s.get('name')) for s in child]==[(s,'season_ticket_'+s) for s in ['up','over','down']]
                            parent.remove(child)
                assert names=={'season_ticket_up','season_ticket_over','season_ticket_down','season_ticket_button'}
                unchanged(before,after,rel+'/'+entry)
            elif entry.endswith('client_strings_ui.xml'):
                before=binary_xml(old.read(entry));after=binary_xml(new.read(entry));new_strings=[e for e in after if e.findtext('name')==shortcut.TOOLTIP]
                assert len(new_strings)==1 and new_strings[0].findtext('body')=='Aetherfall Season Pass'
                after.remove(new_strings[0]);unchanged(before,after,rel+'/'+entry)
            else:
                image=Image.open(io.BytesIO(new.read(entry))).convert('RGBA')
                assert image.size==(128,64) and image.getchannel('A').getextrema()==(0,255)
                assert image.tobytes()==Image.open(out/'ticket-states.png').convert('RGBA').tobytes()
                states=[image.crop((x,0,x+34,32)) for x in [0,40,80]]
                assert all(s.getbbox() for s in states) and len({s.tobytes() for s in states})==3
    lua=read_pak(out/'Plugin/RelicCalc/RelicCalc.pak').read('PrivateMenus.lua').decode('utf-8')
    assert lua.count('RegisterMenu("Aetherfall Season Pass", SLASH_PRIVATESEASONPASS1, "season_ticket_up")')==1
    assert 'SLASH_PRIVATESEASONPASS1 = "/seasonpass"' in lua
    assert 'PrivateWarehouseBrowser:LoadUrlWithWebAuth(PRIVATE_SEASON_PASS_URL)' in lua
    print('OK: native ticket normal/hover/pressed skins, alpha DDS, both base/English HUDs, above-Market placement, English tooltip, authenticated pass route; all unrelated archive entries, skins, strings and widgets preserved.')
