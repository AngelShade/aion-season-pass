"""Season Pass ticket atlas and English tooltip, generated from the original custom artwork."""
import struct
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image,ImageEnhance
from artwork import binary_xml,encode_binary_xml
HERE=Path(__file__).resolve().parent
TOOLTIP='STR_PRIVATE_SEASON_PASS_HUD'

def artwork(out):
    image=Image.open(HERE/'assets/ticket-outlined.png').convert('RGBA')
    if image.getchannel('A').getextrema()!=(0,255):raise ValueError('Ticket requires transparent background')
    image=image.crop(image.getbbox());image.thumbnail((32,30),Image.Resampling.LANCZOS)
    atlas=Image.new('RGBA',(128,64));definitions=[]
    for index,(state,brightness) in enumerate([('up',1),('over',1.28),('down',.72)]):
        icon=ImageEnhance.Brightness(image).enhance(brightness)
        atlas.alpha_composite(icon,(index*40+(34-icon.width)//2,(32-icon.height)//2))
        definitions.append(ET.Element('Skin',name='season_ticket_'+state,src_image=f'{index*40},0,34,32',texture='Textures/UI/season_ticket'))
    preset=ET.Element('Preset',name='season_ticket_button',type='button')
    for state in ('up','over','down'):ET.SubElement(preset,'SkinRef',main_state='0',name='season_ticket_'+state,sub_state=state)
    definitions.append(preset);atlas.save(out/'ticket-states.png')
    header=[124,0x100f,64,128,512,0,0]+[0]*11+[32,0x41,0,32,0xff,0xff00,0xff0000,0xff000000,0x1000,0,0,0,0]
    return definitions,b'DDS '+struct.pack('<31I',*header)+atlas.tobytes()

def strings(data):
    tree=binary_xml(data)
    if any(e.findtext('name')==TOOLTIP or e.findtext('id')=='990100002' for e in tree):raise ValueError('Ticket tooltip already installed')
    entry=ET.SubElement(tree,'string')
    ET.SubElement(entry,'id').text='990100002'
    ET.SubElement(entry,'name').text=TOOLTIP
    ET.SubElement(entry,'body').text='Aetherfall Season Pass'
    return encode_binary_xml(tree)
