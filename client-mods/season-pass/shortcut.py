"""Native ticket skin, both HUD layouts and localized tooltip; unrelated resources preserved."""
import copy
import os
import struct
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageEnhance
from artwork import read_pak, rewrite, binary_xml, encode_binary_xml

HERE=Path(__file__).resolve().parent
RESOURCES=['Data/ui/ui.pak','Textures/ui/ui.pak','L10N/enu/Data/data.pak',
           'Data/ui/game_hud_s1/game_hud_s1.pak','Data/ui/game_hud_s2/game_hud_s2.pak']
TOOLTIP='STR_PRIVATE_SEASON_PASS_HUD'

def artwork(out):
    image=Image.open(HERE/'assets/ticket-outlined.png').convert('RGBA')
    if image.getchannel('A').getextrema()!=(0,255):raise ValueError('Ticket requires transparent background')
    image=image.crop(image.getbbox());image.thumbnail((32,30),Image.Resampling.LANCZOS)
    atlas=Image.new('RGBA',(128,64));defs=[]
    for index,(state,brightness) in enumerate([('up',1),('over',1.28),('down',.72)]):
        icon=ImageEnhance.Brightness(image).enhance(brightness)
        atlas.alpha_composite(icon,(index*40+(34-icon.width)//2,(32-icon.height)//2))
        defs.append(ET.Element('Skin',name='season_ticket_'+state,src_image=f'{index*40},0,34,32',texture='Textures/UI/season_ticket'))
    preset=ET.Element('Preset',name='season_ticket_button',type='button')
    for state in ('up','over','down'):ET.SubElement(preset,'SkinRef',main_state='0',name='season_ticket_'+state,sub_state=state)
    defs.append(preset);atlas.save(out/'ticket-states.png')
    header=[124,0x100f,64,128,512,0,0]+[0]*11+[32,0x41,0,32,0xff,0xff00,0xff0000,0xff000000,0x1000,0,0,0,0]
    return defs,b'DDS '+struct.pack('<31I',*header)+atlas.tobytes()

def library(data,defs):
    tree=binary_xml(data)
    if tree.find(".//Skin[@name='mkt_scales_up']") is None:raise ValueError('Installed Market icon missing')
    if tree.find(".//*[@name='season_ticket_up']") is not None:raise ValueError('Ticket skin already installed')
    category=tree.find(".//Category[@name='version5']")
    if category is None:raise ValueError('Native version5 artwork category missing')
    category.extend(copy.deepcopy(defs));return encode_binary_xml(tree)

def hud(data):
    tree=binary_xml(data);market=tree.find(".//Widget[@name='central_market_button']")
    if tree.get('name')!='start_dialog' or market is None or tree.find(".//Widget[@name='season_pass_button']") is not None:raise ValueError('Unexpected installed HUD')
    x,y,w,h=map(int,market.get('frame').split(','));y-=34
    if y<0:raise ValueError('Ticket would extend beyond HUD')
    ET.SubElement(tree,'Widget',name='season_pass_button',type='button',frame=f'{x},{y},34,32',flag='visible',preset='season_ticket_button',tooltip=TOOLTIP)
    return encode_binary_xml(tree)

def strings(data):
    tree=binary_xml(data)
    if any(e.findtext('name')==TOOLTIP or e.findtext('id')=='990100002' for e in tree):raise ValueError('Ticket tooltip already installed')
    e=ET.SubElement(tree,'string');ET.SubElement(e,'id').text='990100002';ET.SubElement(e,'name').text=TOOLTIP;ET.SubElement(e,'body').text='Aetherfall Season Pass'
    return encode_binary_xml(tree)

def transform(path,rel,defs,dds):
    archive=read_pak(path)
    if rel=='Data/ui/ui.pak':changes={'UI_Preload.xml':library(archive.read('UI_Preload.xml'),defs)}
    elif rel=='Textures/ui/ui.pak':
        if 'season_ticket.dds' in archive.namelist():raise ValueError('Ticket texture already installed')
        changes={'season_ticket.dds':dds}
    elif rel=='L10N/enu/Data/data.pak':
        changes={'ui/ui_preload.xml':library(archive.read('ui/ui_preload.xml'),defs),'strings/client_strings_ui.xml':strings(archive.read('strings/client_strings_ui.xml'))}
        for style in (1,2):
            entry=f'ui/game_hud_s{style}/start_dialog.xml';changes[entry]=hud(archive.read(entry))
    elif rel in RESOURCES:changes={'start_dialog.xml':hud(archive.read('start_dialog.xml'))}
    else:raise ValueError('Unexpected native ticket resource: '+rel)
    return rewrite(path,changes)

def compile_extension(out):
    work=out.parent/(out.name+'-compile');work.mkdir(exist_ok=True)
    dll=out/'bin64/AionMarketShortcut.dll';dll.parent.mkdir(exist_ok=True)
    prebuilt=HERE/'assets/AionMarketShortcut.dll'
    if prebuilt.is_file():
        import shutil
        shutil.copy2(prebuilt,dll)
        return dll.read_bytes()
    vcvars=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'
    source=HERE.parent/'market-shortcut/market_shortcut.cpp'
    script=work/'compile.cmd';script.write_text(f'@echo off\ncall "{vcvars}" >nul\ncl /nologo /std:c++17 /EHsc /O2 /MT /LD /Fo:"{work / "market.obj"}" "{source}" /link /OUT:"{dll}" /IMPLIB:"{work / "market.lib"}"\n')
    subprocess.run(f'cmd.exe /d /s /c ""{script}""',check=True)
    return dll.read_bytes()
