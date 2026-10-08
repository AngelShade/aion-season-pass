"""Prepare all five published Aetherfall mods in one guarded client package."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageEnhance
import struct

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'season-pass'))
import standalone
from standalone import read_pak, rewrite, binary_xml, encode_binary_xml, native, origin_url
MODS=['season-pass','central-market','wardrobe','journey','inventory-warehouse']
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def inventory_modules():
    sys.path.insert(0,str(HERE/'inventory/tools'))
    import inventory_tool
    return inventory_tool
def inventory_dll(original):
    inv=inventory_modules()
    return inv.patch_detached_inventory(inv.patch_warehouse_search_dll(inv.patch_warehouse_dll(inv.patch_search_dll(inv.patch_inventory_dll(original)))))
def merge_native(original,*variants):
    result=bytearray(original);owners={}
    for label,data in variants:
        if len(data)!=len(original): raise ValueError('Native variant size changed: '+label)
        for pos,(old,new) in enumerate(zip(original,data)):
            if old==new:continue
            if pos in owners and result[pos]!=new: raise ValueError(f'Native hook collision at {pos:x}: {owners[pos]} and {label}')
            result[pos]=new;owners[pos]=label
    return bytes(result)
def native_dll(root,origin,mods=None):
    mods=set(MODS if mods is None else mods)
    sys.path.insert(0,str(HERE.parent/'native-icon-bridge'));sys.path.insert(0,str(HERE.parent/'market-shortcut'))
    patch_dll=module('shared_icon_patch',HERE/'native-icon-bridge/patch_client.py').patch_dll
    from patch_binary import patch
    original=(root/'bin64/Game.dll').read_bytes()
    routes=[origin+route for feature,route in [('central-market','/market'),('wardrobe','/market/wardrobe'),('season-pass','/market/pass'),('journey','/journey')] if feature in mods]
    browser=native.build_dll(root/'bin64/Game.dll',[],routes) if routes else original
    variants=[('browser',browser)]
    if 'inventory-warehouse' in mods: variants.append(('inventory',inventory_dll(original)))
    dll=merge_native(original,*variants)
    dll,hooks=patch(patch_dll(dll))
    return dll,hooks,routes
def market_artwork():
    image=Image.open(HERE/'scales-outlined.png').convert('RGBA');image=image.crop(image.getbbox());image.thumbnail((32,34),Image.Resampling.LANCZOS)
    atlas=Image.new('RGBA',(128,64));definitions=[]
    for index,(state,brightness) in enumerate([('up',1),('over',1.28),('down',.72)]):
        atlas.alpha_composite(ImageEnhance.Brightness(image).enhance(brightness),(index*40+(34-image.width)//2,(36-image.height)//2))
        definitions.append(ET.Element('Skin',name='mkt_scales_'+state,src_image=f'{index*40},0,34,36',texture='Textures/UI/mkt_scales'))
    preset=ET.Element('Preset',name='mkt_scales_button',type='button')
    for state in ['up','over','down']:ET.SubElement(preset,'SkinRef',main_state='0',name='mkt_scales_'+state,sub_state=state)
    definitions.append(preset)
    header=[124,0x100f,64,128,512,0,0]+[0]*11+[32,0x41,0,32,0xff,0xff00,0xff0000,0xff000000,0x1000,0,0,0,0]
    return definitions,b'DDS '+struct.pack('<31I',*header)+atlas.tobytes()
def hud(data,style,mods):
    tree=binary_xml(data)
    season=tree.find(".//Widget[@name='season_pass_button']");assert season is not None
    if 'season-pass' in mods:
        if 'central-market' in mods: season.set('frame','26,53,34,32' if style==1 else '39,35,34,32')
    else:
        for parent in tree.iter():
            if season in list(parent): parent.remove(season);break
    if 'central-market' in mods:
        ET.SubElement(tree,'Widget',name='central_market_button',type='button',frame='64,53,34,36' if style==1 else '77,35,34,36',flag='visible',preset='mkt_scales_button',tooltip='Central Market')
    return encode_binary_xml(tree)
def staged_rewrite(output,relative,changes):
    path=output/relative;data=rewrite(path,changes);path.write_bytes(data)
def known_install(target,original):
    if target==original:return set(),set()
    if digest(target/'bin64/Game.dll')==native.ORIGINAL_SHA256:return set(),set()
    records=[]
    receipt=target/'Aetherfall-mods.json'
    if receipt.is_file():records.append(json.loads(receipt.read_text()))
    for directory,name in [('SeasonPass-backups','manifest.json'),('TransmogMenu-backups','manifest.json'),('Inventory-backups','backup.json')]:
        for path in sorted((target/directory).glob('*/'+name),reverse=True):
            records.append(json.loads(path.read_text(encoding='utf-8-sig')))
    for record in records:
        files=record.get('files',[])
        if not files or not any(e['path'].lower()=='bin64/game.dll' for e in files):continue
        if not all((target/e['path']).is_file() and digest(target/e['path'])==e.get('installed',e.get('staged')) for e in files):continue
        features=set(record.get('mods',[]))
        if record.get('feature')=='daeva-season-pass':features.add('season-pass')
        if record.get('wardrobe'):features.add('wardrobe')
        if record.get('poetaJourney'):features.add('journey')
        if record.get('marketHud') or (record.get('nativeIcons') and not features):features.add('central-market')
        if record.get('kind')=='client':features.add('inventory-warehouse')
        if not features or not features.issubset(MODS):continue
        return features,{e['path'].lower() for e in files}
    raise ValueError('Existing client is not a verified published-mod installation. Preserve it and use a separate original client, or restore its standalone package with its own guarded restore tool.')
def prepare(client,output,url,original_client=None,mods=None):
    target,output=client.resolve(),output.resolve();root=(original_client or client).resolve()
    if output.exists() or any(output==p or p in output.parents or output in p.parents for p in [target,root]):raise ValueError('Use a new staging directory outside both clients')
    origin,_=origin_url(url)
    snapshot=root/'original-inputs.json'
    if snapshot.is_file():
        for entry in json.loads(snapshot.read_text())['files']:
            if digest(root/entry['path'])!=entry['sha256']:raise ValueError('Saved original client input changed: '+entry['path'])
    previous,known=known_install(target,root)
    selected=set(MODS if mods is None else mods)
    if not selected or not selected.issubset(MODS):raise ValueError('Choose a supported module')
    selected.update(previous)
    mods=[m for m in MODS if m in selected]
    if digest(root/'bin64/Game.dll')!=native.ORIGINAL_SHA256:raise ValueError('The original-client input must have the supported stock Game.dll')
    # These unmanaged renderer/companion modifications have their own cumulative recovery guards.
    if any((target/p).exists() for p in ['DXVK/installed.json','DXVK/graphics-menu/installed.json','bin64/PlayerBotBridge.dll']):
        raise ValueError('Use a separate client: this shared release does not migrate private renderer or companion integrations')
    media=output.parent/(output.name+'-server-media')
    if media.exists():raise ValueError('Generated server media directory already exists')
    for name in (['loading_lf1.dds','loading_lc1.dds','loading_df1.dds','loading_dc1.dds'] if 'journey' in mods else []):
        if not (root/'Textures/loading'/name).is_file():raise ValueError('Original Journey loading artwork is required: '+name)
    output.parent.mkdir(parents=True,exist_ok=True)
    tempfile.tempdir=str(output.parent)
    standalone.prepare(root,output,origin)
    changes={}
    for kind,name in [('wardrobe','Wardrobe.xml'),('journey','Journey.xml')]:
        if kind not in mods:continue
        data=(HERE/kind/name).read_text(encoding='utf-8-sig').replace('UTF-8','UTF-16').replace('\n','\r\n').encode('utf-16');ET.fromstring(data);changes[name]=data
    with read_pak(output/'Plugin/RelicCalc/RelicCalc.pak') as archive:
        toc=archive.read('RelicCalc.toc').decode().replace('\r','').splitlines()
    toc=[line for line in toc if line!='PrivateMenus.lua']+list(changes)+['PrivateMenus.lua']
    changes['RelicCalc.toc']=('\r\n'.join(toc)+'\r\n').encode()
    menu=(HERE/'PrivateMenus.lua').read_text().replace('@ORIGIN@',origin)
    commands={'season-pass':'PRIVATESEASONPASS','central-market':'PRIVATEMARKET','wardrobe':'PRIVATEWARDROBE','journey':'PRIVATEJOURNEY'}
    menu='\n'.join(line for line in menu.splitlines() if not any(command in line for feature,command in commands.items() if feature not in mods))+'\n'
    changes['PrivateMenus.lua']=menu.replace('\n','\r\n').encode()
    staged_rewrite(output,'Plugin/RelicCalc/RelicCalc.pak',changes)
    definitions,texture=market_artwork()
    with read_pak(output/'Data/ui/ui.pak') as archive:data=standalone.library(archive.read('UI_Preload.xml'),definitions)
    staged_rewrite(output,'Data/ui/ui.pak',{'UI_Preload.xml':data})
    staged_rewrite(output,'Textures/ui/ui.pak',{'mkt_scales.dds':texture})
    locale='L10N/enu/Data/data.pak'
    with read_pak(output/locale) as archive:
        changes={'ui/ui_preload.xml':standalone.library(archive.read('ui/ui_preload.xml'),definitions)}
        for style in [1,2]:
            name=f'ui/game_hud_s{style}/start_dialog.xml';changes[name]=hud(archive.read(name),style,mods)
    staged_rewrite(output,locale,changes)
    for style in [1,2]:
        relative=f'Data/ui/game_hud_s{style}/game_hud_s{style}.pak'
        with read_pak(output/relative) as archive:data=hud(archive.read('start_dialog.xml'),style,mods)
        staged_rewrite(output,relative,{'start_dialog.xml':data})
    if 'wardrobe' in mods:
        wardrobe=module('shared_wardrobe_item',HERE/'wardrobe/wardrobe_item.py');wardrobe.prepare_wardrobe_item(root,output)
    else:
        path=output/'Data/Items/Items.pak';path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/'Data/Items/Items.pak',path)
    inv=inventory_modules()
    for relative,prefix in ([('Data/ui/game/game.pak',''),(locale,'ui/game/')] if 'inventory-warehouse' in mods else []):
        path=output/relative;source=path if path.exists() else root/relative
        data=inv.patch_warehouse_archive(inv.patch_archive(source.read_bytes(),prefix),prefix)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    sys.path.insert(0,str(HERE.parent/'native-icon-bridge'));sys.path.insert(0,str(HERE.parent/'market-shortcut'))
    from build_bridge import build as bridge
    stats=bridge(root,output,origin,source_dir=HERE/'native-icon-bridge',index_client=output)
    existing=json.loads((output/'manifest.json').read_text());existing['nativeIcons']=stats
    dll,hooks,routes=native_dll(root,origin,mods);(output/'bin64/Game.dll').write_bytes(dll)
    standalone.compile_shortcut(output,source=HERE/'shared_shortcut.cpp',suffix='shared')
    subprocess.run(['java',str(HERE.parent/'transmog-menu/SignClientPackages.java'),str(root),str(output)],check=True)
    (output/'Pub.key').unlink()
    files=[]
    for path in sorted(output.rglob('*')):
        if not path.is_file() or path.name=='manifest.json':continue
        relative=path.relative_to(output).as_posix();current=target/relative;stock=root/relative
        if target!=root and current.is_file() and relative.lower() not in known and (not stock.is_file() or digest(current)!=digest(stock)):
            raise ValueError('Unrecorded client modification would be overwritten: '+relative)
        files.append(dict(path=relative,original=digest(current) if current.is_file() else None,installed=digest(path)))
    preserved=['Pub.key','bin32/bin32.pak','Data/func_pet/func_pet.pak','bin64/Awesomium.dll']
    for relative in preserved:
        if digest(target/relative)!=digest(root/relative):raise ValueError('Stock input differs between original and target: '+relative)
    receipt=dict(version=1,mods=mods,originalClient=str(root),serverUrl=origin,files=files)
    record=output/'Aetherfall-mods.json';record.write_text(json.dumps(receipt,indent=2)+'\n')
    files.append(dict(path=record.name,original=digest(target/record.name) if (target/record.name).is_file() else None,installed=digest(record)))
    manifest=dict(feature='daeva-season-pass',mode='shared-mods',mods=mods,previousMods=sorted(previous),clientRoot=str(target),originalClient=str(root),serverUrl=origin,sourceKey=digest(root/'Pub.key'),files=files,preservedFiles=[dict(path=p,sha256=digest(target/p)) for p in preserved],nativeIcons=existing['nativeIcons'],hooks={'bin64/Game.dll':hooks},routes=routes)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if 'journey' in mods:media.mkdir()
    for source,name in ([('loading_lf1.dds','poeta.jpg'),('loading_lc1.dds','sanctum.jpg'),('loading_df1.dds','ishalgen.jpg'),('loading_dc1.dds','pandaemonium.jpg')] if 'journey' in mods else []):
        with Image.open(root/'Textures/loading'/source) as image:image.convert('RGB').save(media/name,quality=92)
    print('OK: cumulative client modules prepared:',mods,'; existing mods retained:',sorted(previous))
    if 'journey' in mods:print('Copy locally generated Journey artwork to server config/journey/media:',media)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--client',type=Path,required=True);parser.add_argument('--original-client',type=Path);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--server-url',required=True);parser.add_argument('--mods',nargs='+',choices=MODS);args=parser.parse_args()
    prepare(args.client,args.output,args.server_url,args.original_client,args.mods)
