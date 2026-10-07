"""Slice generated UI artwork into native tiled skins; preserve stock resources."""
import copy,io,json,struct,zipfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from build_package import read_pak,binary_xml,encode_binary_xml,encode_pak,HERE
from xml.etree import ElementTree as ET

ASSETS=('Data/ui/ui.pak','Textures/ui/ui.pak')
# Resize/crop coordinates are production slice boundaries, not painted artwork.
# The eleven-part native skin keeps the tail fixed in the bottom center.
CONFIG={
 'ornate':dict(size=(168,84),left=36,right=36,top=24,bottom=34,tail=(70,98)),
 'amber':dict(size=(128,64),left=19,right=19,top=20,bottom=32,tail=(52,80)),
 'thought':dict(size=(180,120),left=46,right=46,top=35,bottom=46,tail=(80,100)),
}

def make_skins(out):
    definitions=[];textures={};preview=Image.new('RGBA',(800,380),(20,30,42,255));d=ImageDraw.Draw(preview)
    for row,(name,c) in enumerate(CONFIG.items()):
        image=Image.open(HERE/'assets'/f'{name}.png').convert('RGBA').resize(c['size'],Image.Resampling.LANCZOS)
        w,h=image.size;l,r,t,b=[c[k] for k in ('left','right','top','bottom')];a,z=c['tail'];y=h-b
        rects={
          'left_top':(0,0,l,t),'middle_top':(l,0,w-r,t),'right_top':(w-r,0,w,t),
          'left_middle':(0,t,l,y),'middle_middle':(l,t,w-r,y),'right_middle':(w-r,t,w,y),
          'left_bottom':(0,y,l,h),'middle_bottom_left':(l,y,a,h),
          'middle_bottom':(a,y,z,h),'middle_bottom_right':(z,y,w-r,h),'right_bottom':(w-r,y,w,h)}
        atlas=Image.new('RGBA',(512,256));skin=ET.Element('Skin',name='asb_'+name,type='tiled',texture='Textures/UI/asb_'+name)
        parts={};x=2;ay=2;line_height=0
        for part,rect in rects.items():
            tile=image.crop(rect);pw,ph=tile.size
            if x+pw+2>512:x=2;ay+=line_height+4;line_height=0
            assert ay+ph+2<=256
            atlas.paste(tile,(x,ay));skin.set('src_'+part,f'{x},{ay},{pw},{ph}')
            dw=0 if part in ('middle_top','middle_middle','middle_bottom_left','middle_bottom_right') else pw
            dh=0 if part.endswith('middle') else ph
            skin.set('size_'+part,f'{dw},{dh}');parts[part]=(tile,dw,dh)
            x+=pw+4;line_height=max(line_height,ph)
        # Legacy D3D9 DDS with explicit RGBA masks, no DX10 header/compression.
        header=[124,0x100f,256,512,512*4,0,0]+[0]*11+[32,0x41,0,32,0xff,0xff00,0xff0000,0xff000000,0x1000,0,0,0,0]
        textures['asb_'+name+'.dds']=b'DDS '+struct.pack('<31I',*header)+atlas.tobytes()
        definitions.append(skin)
        atlas.save(out/('atlas-'+name+'.png'))
        for col,width in enumerate(({'ornate':126,'amber':108,'thought':142}[name],270)):
            height={'ornate':82,'amber':72,'thought':108}[name];canvas=render(parts,width,height,l,r,t,b,z-a)
            preview.alpha_composite(canvas,(25+col*370,15+row*122))
            text='test' if col==0 else 'A longer chat message';box=d.textbbox((0,0),text)
            d.text((25+col*370+(width-(box[2]-box[0]))/2,15+row*122+t+3),text,fill='white')
    preview.save(out/'styles-preview.png')
    xml=ET.Element('Skins');xml.extend(definitions)
    (out/'skin-definitions.xml').write_bytes(ET.tostring(xml,encoding='utf-8'))
    return definitions,textures

def render(parts,w,h,l,r,t,b,tail):
    mid=w-l-r;split=(mid-tail)//2
    positions={
     'left_top':(0,0,l,t),'middle_top':(l,0,mid,t),'right_top':(w-r,0,r,t),
     'left_middle':(0,t,l,h-t-b),'middle_middle':(l,t,mid,h-t-b),'right_middle':(w-r,t,r,h-t-b),
     'left_bottom':(0,h-b,l,b),'middle_bottom_left':(l,h-b,split,b),
     'middle_bottom':(l+split,h-b,tail,b),'middle_bottom_right':(l+split+tail,h-b,mid-split-tail,b),
     'right_bottom':(w-r,h-b,r,b)}
    dest=Image.new('RGBA',(w,h))
    for part,(x,y,pw,ph) in positions.items():
        tile=parts[part][0].resize((pw,ph),Image.Resampling.LANCZOS);dest.alpha_composite(tile,(x,y))
    return dest

def rewrite(source,replacements):
    z=read_pak(source);buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as target:
        for info in z.infolist():target.writestr(info,replacements.get(info.filename,z.read(info.filename)))
        for name,data in replacements.items():
            if name not in z.namelist():target.writestr(name,data)
    return encode_pak(buf.getvalue())

def skins_xml(payload,definitions):
    root=binary_xml(payload);category=root.find(".//Category[@name='free_version']")
    if root.tag!='SkinLibrary' or category is None:raise ValueError('Unexpected native skin library')
    for skin in definitions:
        if root.find(".//Skin[@name='"+skin.get('name')+"']") is not None:raise ValueError('Custom skin already exists')
        category.append(copy.deepcopy(skin))
    return encode_binary_xml(root)

def patch_resources(base_ui,base_textures,english,out):
    out.mkdir(parents=True,exist_ok=True);defs,textures=make_skins(out)
    library=read_pak(base_ui);locale=read_pak(english)
    return {
     'Data/ui/ui.pak':rewrite(base_ui,{'UI_Preload.xml':skins_xml(library.read('UI_Preload.xml'),defs)}),
     'Textures/ui/ui.pak':rewrite(base_textures,textures),
     'L10N/enu/Data/data.pak':rewrite(english,{'ui/ui_preload.xml':skins_xml(locale.read('ui/ui_preload.xml'),defs)})}
