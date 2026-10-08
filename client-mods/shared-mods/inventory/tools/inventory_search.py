"""Native item-name search for the verified 4.8 inventory.

Search changes drawing and the scrollbar only. Slot IDs, item bindings, saved
positions, item actions, and packet serialization remain native.
"""
import struct
import xml.etree.ElementTree as ET

from patch_game_dll import Assembler
from unified_inventory import INVENTORY_VTABLE, SLOTS, GRID_HEIGHT, VISIBLE_GRID_HEIGHT

MATCH = 0x144e100
POLL = 0x144e200
BUTTON = 0x144e900
DRAW = 0x144eb00
STATE = 0x144ec00
STRINGS = 0x144ee00
POLL_SITE = 0x7857b7
BUTTON_SITE = 0x7867f0
DRAW_SITE = 0x4f2079

# State: list pointer, reserved bytes, query length, saved thumb,
# match count, 279 match flags, bounded UTF-16 query, and status text.
FLAGS, QUERY, STATUS = 0x28, 0x140, 0x1c0
TEXTS = {}
_strings = bytearray()
for _name, _text, _wide in [
    ('edit', 'inventory_search', False),
    ('clear', 'inventory_search_clear', False),
    ('count', 'inventory_search_count', False),
    ('bar', 'inv_scroll', False),
    ('viewport', 'inv_scrollable', False),
    ('empty', '', True),
    ('none', 'No matches', True),
]:
    if _wide and len(_strings) % 2:
        _strings.append(0)
    TEXTS[_name] = STRINGS + len(_strings)
    _strings.extend((_text + '\0').encode('utf-16le' if _wide else 'ascii'))


def hexcode(asm, value):
    asm.emit(bytes.fromhex(value))


def widget(asm, name, kind):
    # r12 owns the inventory dialog. Native lookup follows its active tab.
    hexcode(asm, '4c89e1498b0424')
    asm.relative(b'\x48\x8d\x15', TEXTS[name])
    asm.emit(b'\x41\xb8' + struct.pack('<I', kind))
    hexcode(asm, 'ff9038030000')


def match_code():
    """Bounded substring match; English names ignore ASCII letter case."""
    a = Assembler(MATCH)
    hexcode(a, '4531c9')  # start index
    a.label('start')
    hexcode(a, '4181f900020000')  # at most 512 name characters
    a.branch(b'\x0f\x83', 'miss')
    hexcode(a, '420fb704494531c0')
    hexcode(a, '85c0')
    a.branch(b'\x0f\x84', 'miss')
    a.label('char')
    hexcode(a, '4183f83f')
    a.branch(b'\x0f\x83', 'hit')
    hexcode(a, '460fb714424585d2')
    a.branch(b'\x0f\x84', 'hit')
    hexcode(a, '4589cb4501c34181fb00020000')
    a.branch(b'\x0f\x83', 'miss')
    hexcode(a, '420fb7045985c0')
    a.branch(b'\x0f\x84', 'miss')
    hexcode(a, '83f841')
    a.branch(b'\x0f\x82', 'query_fold')
    hexcode(a, '83f85a')
    a.branch(b'\x0f\x87', 'query_fold')
    hexcode(a, '83c020')
    a.label('query_fold')
    hexcode(a, '4183fa41')
    a.branch(b'\x0f\x82', 'compare')
    hexcode(a, '4183fa5a')
    a.branch(b'\x0f\x87', 'compare')
    hexcode(a, '4183c220')
    a.label('compare')
    hexcode(a, '4439d0')
    a.branch(b'\x0f\x85', 'advance')
    hexcode(a, '41ffc0')
    a.branch(b'\xe9', 'char')
    a.label('advance')
    hexcode(a, '41ffc1')
    a.branch(b'\xe9', 'start')
    a.label('hit')
    hexcode(a, 'b801000000c3')
    a.label('miss')
    hexcode(a, '31c0c3')
    return a.finish()


def poll_code():
    a = Assembler(POLL)
    # Eight saved registers plus 0x68 bytes keep Windows call alignment.
    hexcode(a, '5355565741544155415641574883ec684989cc')
    a.relative(b'\x48\x8d\x1d', STATE)
    a.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    hexcode(a, '49390424')
    a.branch(b'\x0f\x85', 'done')
    hexcode(a, 'c7442424000000008b431089442428')  # changed / previous query length
    hexcode(a, '4d8bb424880500004d85f6')
    a.branch(b'\x0f\x84', 'done')
    hexcode(a, '4c3933')
    a.branch(b'\x0f\x84', 'lookup')
    hexcode(a, '4c8933c744242401000000')
    a.label('lookup')
    widget(a, 'edit', 0x200b)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'done')
    hexcode(a, 'c7800c0400003f0000004889c1488b00ff90980200004885c0')
    a.branch(b'\x0f\x84', 'done')
    hexcode(a, '4889c64531ff')
    a.label('leading')
    hexcode(a, '66833e20')
    a.branch(b'\x0f\x85', 'copy')
    hexcode(a, '4883c60241ffc74183ff3f')
    a.branch(b'\x0f\x82', 'leading')
    a.label('copy')
    hexcode(a, '31ff')
    a.label('copy_char')
    hexcode(a, '31c083ff3f')
    a.branch(b'\x0f\x83', 'copy_zero')
    hexcode(a, '0fb7047e')
    a.label('copy_zero')
    hexcode(a, '6639847b40010000')
    a.branch(b'\x0f\x84', 'store')
    hexcode(a, 'c744242401000000')
    a.label('store')
    hexcode(a, '6689847b4001000085c0')
    a.branch(b'\x0f\x84', 'copied')
    hexcode(a, 'ffc7')
    a.branch(b'\xe9', 'copy_char')
    a.label('copied')
    hexcode(a, '897b10')
    # Empty query restores the thumb saved when search began.
    hexcode(a, '85ff')
    a.branch(b'\x0f\x85', 'save_scroll')
    hexcode(a, '4531ed837c242800')
    a.branch(b'\x0f\x84', 'status')
    widget(a, 'bar', 0x201e)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'status')
    hexcode(a, '8b5314899034040000')
    a.branch(b'\xe9', 'layout')
    a.label('save_scroll')
    hexcode(a, '837c242800')
    a.branch(b'\x0f\x85', 'scan_setup')
    widget(a, 'bar', 0x201e)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'scan_setup')
    hexcode(a, '8b8034040000894314')
    a.label('scan_setup')
    # Clear flags even when the native vector is shorter or an item was removed.
    hexcode(a, '488d7b2831c0b9')
    a.emit(struct.pack('<I', SLOTS))
    hexcode(a, 'f3aa4531ff4531edbdffffffff')
    a.label('scan')
    hexcode(a, '4181ff')
    a.emit(struct.pack('<I', SLOTS))
    a.branch(b'\x0f\x83', 'scanned')
    hexcode(a, '498b86b80300004885c0')
    a.branch(b'\x0f\x84', 'scanned')
    hexcode(a, '498b8ec00300004829c148c1e9034939cf')
    a.branch(b'\x0f\x83', 'scanned')
    hexcode(a, '4a8b3cf84885ff')
    a.branch(b'\x0f\x84', 'step')
    hexcode(a, '448b87940000004585c0')
    a.branch(b'\x0f\x84', 'step')
    a.relative(b'\x48\x8b\x0d', 0x12eda48)
    hexcode(a, '4885c9')
    a.branch(b'\x0f\x84', 'step')
    hexcode(a, '8b97980000004531c9')
    a.relative(b'\xe8', 0x444030)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'step')
    hexcode(a, '488d48204883783808')
    a.branch(b'\x0f\x82', 'name')
    hexcode(a, '488b4820')
    a.label('name')
    hexcode(a, '4885c9')
    a.branch(b'\x0f\x84', 'step')
    hexcode(a, '488d9340010000')
    a.relative(b'\xe8', MATCH)
    hexcode(a, '85c0')
    a.branch(b'\x0f\x84', 'step')
    hexcode(a, '42c6443b280141ffc583fdff')
    a.branch(b'\x0f\x85', 'step')
    hexcode(a, '4489fd')
    a.label('step')
    hexcode(a, '41ffc7')
    a.branch(b'\xe9', 'scan')
    a.label('scanned')
    hexcode(a, '837c242400')
    a.branch(b'\x0f\x84', 'status')
    hexcode(a, '83fdff')
    a.branch(b'\x0f\x84', 'status')
    widget(a, 'bar', 0x201e)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'status')
    hexcode(a, '4889c689e831d2b90c000000f7f16bc02b8944242c')
    widget(a, 'viewport', 0x201d)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'status')
    hexcode(a, '498b9424b00500004885d2')
    a.branch(b'\x0f\x84', 'status')
    # Use actual scaled grid and viewport heights, including a resized window.
    hexcode(a, 'f20f104a68f20f10d1f20f5c9088000000660fefdb660f2fd3')
    a.branch(b'\x0f\x86', 'status')
    hexcode(a, 'f20f2a44242cf20f59c1')
    a.branch(b'\xf2\x0f\x5e\x05', 'grid_height')
    hexcode(a, 'f20f5ec2')
    a.branch(b'\xf2\x0f\x5d\x05', 'one')
    hexcode(a, 'f20f5ac0f30f118634040000')
    a.label('layout')
    hexcode(a, '4c89e1498b042431d2ff9098060000')
    a.label('status')
    # Only replace text when the count/query changes.
    hexcode(a, '44396b18')
    a.branch(b'\x0f\x85', 'status_update')
    hexcode(a, '837c242400')
    a.branch(b'\x0f\x84', 'done')
    a.label('status_update')
    hexcode(a, '44896b18')
    widget(a, 'count', 0x2022)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'done')
    hexcode(a, '4889c6837b1000')
    a.branch(b'\x0f\x84', 'empty_status')
    hexcode(a, '4585ed')
    a.branch(b'\x0f\x84', 'none_status')
    # A three-digit decimal count followed by matches.
    hexcode(a, '488dbbc00100004489e8b96400000031d2f7f183c030668907')
    hexcode(a, '89d0b90a00000031d2f7f183c0306689470283c23066895704')
    hexcode(a, '48b820006d00610074004889470648b863006800650073004889470e66c747160000')
    hexcode(a, '4889fa66833a30')
    a.branch(b'\x0f\x85', 'set_status')
    hexcode(a, '4883c20266833a30')
    a.branch(b'\x0f\x85', 'set_status')
    hexcode(a, '4883c202')
    a.branch(b'\xe9', 'set_status')
    a.label('none_status')
    a.relative(b'\x48\x8d\x15', TEXTS['none'])
    a.branch(b'\xe9', 'set_status')
    a.label('empty_status')
    a.relative(b'\x48\x8d\x15', TEXTS['empty'])
    a.label('set_status')
    hexcode(a, '4889f1488b06ff9090020000')
    a.label('done')
    hexcode(a, '4883c468415f415e415d415c5f5e5d5bc3')
    a.label('grid_height')
    a.emit(struct.pack('<d', GRID_HEIGHT))
    a.label('one')
    a.emit(struct.pack('<d', 1.0))
    return a.finish()


def button_code():
    a = Assembler(BUTTON)
    hexcode(a, '535641544883ec304989cc4889d3')
    a.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    hexcode(a, '483901')
    a.branch(b'\x0f\x85', 'original')
    hexcode(a, '4885d2')
    a.branch(b'\x0f\x84', 'original')
    hexcode(a, '488b324885f6')
    a.branch(b'\x0f\x84', 'original')
    widget(a, 'clear', 0x2001)
    hexcode(a, '4839f0')
    a.branch(b'\x0f\x85', 'original')
    widget(a, 'edit', 0x200b)
    hexcode(a, '4885c0')
    a.branch(b'\x0f\x84', 'handled')
    hexcode(a, '4889c1488b00')
    a.relative(b'\x48\x8d\x15', TEXTS['empty'])
    hexcode(a, 'ff9090020000')
    a.label('handled')
    hexcode(a, 'b8010000004883c430415c5e5bc3')
    a.label('original')
    hexcode(a, '4c89e14889da4883c430415c5e5b4889e04881ec98040000')
    a.relative(b'\xe9', BUTTON_SITE + 10)
    return a.finish()


def draw_code():
    a = Assembler(DRAW)
    hexcode(a, '5052')
    a.relative(b'\x48\x8d\x05', STATE)
    hexcode(a, '83781000')
    a.branch(b'\x0f\x84', 'done')
    hexcode(a, '488b13483b10')  # exact native list owner, no other item views
    a.branch(b'\x0f\x85', 'done')
    hexcode(a, '8b939000000081fa')
    a.emit(struct.pack('<I', SLOTS))
    a.branch(b'\x0f\x83', 'done')
    hexcode(a, '807c102800')
    a.branch(b'\x0f\x85', 'done')
    for reg in (10, 11, 12):
        a.branch(b'\xf3\x44\x0f\x59' + bytes([0x05 | ((reg & 7) << 3)]), 'dim')
    a.label('done')
    hexcode(a, '5a58f20f118c24c8000000')
    a.relative(b'\xe9', DRAW_SITE + 9)
    a.label('dim')
    a.emit(struct.pack('<f', 0.28))
    return a.finish()


def patch_search_dll(payload):
    data = bytearray(payload)
    for site, old, cave, length in [
        (POLL_SITE, bytes.fromhex('e8c47cd2ff'), POLL, 5),
        (BUTTON_SITE, bytes.fromhex('488bc44881ec98040000'), BUTTON, 10),
        (DRAW_SITE, bytes.fromhex('f20f118c24c8000000'), DRAW, 9),
    ]:
        if data[site:site + length] != old:
            raise ValueError(f'Unsupported inventory search instruction at {site:x}')
        # Poll must retain the original base drawing call and its return value.
        if site == POLL_SITE:
            continue
        data[site:site + length] = b'\xe9' + struct.pack('<i', cave - site - 5) + b'\x90' * (length - 5)
    # The existing caller supplies rcx=inventory and already owns shadow space.
    # A short wrapper preserves it across the poll and tail-calls base drawing.
    wrapper = Assembler(STRINGS + 0x100)
    hexcode(wrapper, '514883ec20')
    wrapper.relative(b'\xe8', POLL)
    hexcode(wrapper, '4883c42059')
    wrapper.relative(b'\xe9', 0x4ad480)
    data[POLL_SITE:POLL_SITE + 5] = b'\xe8' + struct.pack('<i', wrapper.base - POLL_SITE - 5)
    for start, code, end in [
        (MATCH, match_code(), POLL), (POLL, poll_code(), BUTTON),
        (BUTTON, button_code(), DRAW), (DRAW, draw_code(), STATE),
        (STATE, bytes(0x200), STRINGS), (STRINGS, bytes(_strings), STRINGS + 0x100),
        (wrapper.base, wrapper.finish(), 0x144f000),
    ]:
        if start + len(code) > end or any(data[start:start + len(code)]):
            raise ValueError(f'Inventory search code/state exceeds verified padding at {start:x}')
        data[start:start + len(code)] = code
    return bytes(data)


def patch_search_layout(root):
    """Use the game's editbox, buttons, and fonts above the native footer."""
    bottom = root.find("Widget[@name='bottom']")
    bottom.set('frame', '0,590,556,64')
    for widget in list(bottom):
        if widget.get('name', '').startswith('inventory_search'):
            bottom.remove(widget)
            continue
        x, y, w, h = map(int, widget.get('frame').split(','))
        # Base layout resets these Y positions before applying this patch.
        widget.set('frame', f'{x},{y + 34},{w},{h}')
    for attrs in [
        dict(type='static', name='inventory_search_label', frame='8,4,54,24',
             text='STR_WHO_DIALOG__SEARCH', font='ui_default', valign='middle'),
        dict(type='editbox', name='inventory_search', frame='64,4,300,24',
             preset='v5_editbox', font='ui_editbox', h_padding='4', v_padding='4',
             alphanumeric='False', tabstop='1', max_length='63'),
        dict(type='button', name='inventory_search_clear', frame='366,4,58,24',
             preset='v5_button', font='ui_default', text='STR_PARTY_MATCH_DIALOG__SEARCH_CANCEL',
             tooltip='STR_PARTY_MATCH_DIALOG__SEARCH_CANCEL'),
        dict(type='static', name='inventory_search_count', frame='430,4,118,24',
             font='ui_default', valign='middle', halign='right'),
    ]:
        ET.SubElement(bottom, 'Widget', attrs)
    return root
