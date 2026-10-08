"""Version-checked native inventory layout and slot bounds for the 4.8 NA client."""
import io
import struct
import zipfile
import xml.etree.ElementTree as ET

from patch_game_dll import Assembler

BASE_SLOTS = 180
MAX_EXPANSIONS = 11
SLOTS = BASE_SLOTS + MAX_EXPANSIONS * 9
GRID_HEIGHT = ((SLOTS + 11) // 12) * 43 + 5
INVENTORY_VTABLE = 0xcbe468
INIT_SITE, INIT_CAVE = 0x7843dd, 0x144dd00
UPDATE_SITE, UPDATE_CAVE = 0x785026, 0x144dd80
OPEN_SITE, OPEN_CAVE = 0x784d21, 0x144de00
LAYOUT_SITE, LAYOUT_CAVE = 0x7894ad, 0x144df80
SCROLL_SITE, SCROLL_CAVE = 0x789778, 0x144e000
VISIBLE_GRID_HEIGHT = 392  # Nine complete rows (108 slots) before scrolling.
EFFECT_LOOPS = [(0x788c9e, 0x788b30, 0x788ca8, 0x144de80),
                (0x788ea5, 0x788d51, 0x788eaf, 0x144df00)]


def effect_loop_code(cave, target, exit_target):
    bound = Assembler(cave)
    bound.emit(b'\x48\x81\xfd' + struct.pack('<I', SLOTS))
    bound.relative(b'\x0f\x8c', target)
    bound.relative(b'\xe9', exit_target)
    return bound.finish()


def layout_code():
    layout = Assembler(LAYOUT_CAVE)
    layout.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    layout.emit(b'\x49\x39\x04\x24')  # r12 is the native inventory dialog
    layout.branch(b'\x0f\x85', 'original')
    layout.emit(b'\x66\x0f\xef\xc9')  # xmm1 = native zero padding
    layout.branch(b'\xf2\x0f\x10\x05', 'height')  # visible fraction of full grid
    # xmm9 holds the first grid's actual scaled height. xmm15 is native spacing (2).
    layout.emit(b'\xf2\x41\x0f\x59\xc1')  # multiply by scaled grid height xmm9
    layout.emit(b'\x31\xdb\xbd\x01\0\0\0')  # scrollbar off; native ebp = 1
    layout.emit(b'\x66\x44\x0f\x2f\xe0')  # comisd xmm12, xmm0
    layout.branch(b'\x0f\x86', 'done')
    layout.emit(b'\xf2\x44\x0f\x10\xe0\xb3\x01')  # clamp viewport, enable scroll
    layout.label('done')
    layout.relative(b'\xe9', 0x78952d)
    layout.label('original')
    layout.emit(bytes.fromhex('66450f2fc1'))
    layout.relative(b'\xe9', LAYOUT_SITE + 5)
    layout.label('height')
    layout.emit(struct.pack('<d', VISIBLE_GRID_HEIGHT / GRID_HEIGHT))
    return layout.finish()


def scroll_code():
    scroll = Assembler(SCROLL_CAVE)
    scroll.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    scroll.emit(bytes.fromhex('49390424'))
    scroll.branch(b'\x0f\x85', 'original')
    # Keep the native thumb fraction. The cube routine derives it from the
    # viewport's layout origin (+0x78), which is always zero for this grid.
    scroll.emit(bytes.fromhex('f2410f10f3f20f5cb788000000f2410f59f2'))
    scroll.emit(bytes.fromhex('f2440f10cef2440f588f88000000'))
    scroll.relative(b'\xe9', 0x7897f8)
    scroll.label('original')
    scroll.emit(bytes.fromhex('498b0424ff9090060000'))
    scroll.relative(b'\xe9', SCROLL_SITE + 6)
    return scroll.finish()


def inventory_code():
    init = Assembler(INIT_CAVE)
    init.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    init.emit(b'\x49\x39\x04\x24')  # normal inventory's concrete vtable only
    init.branch(b'\x0f\x85', 'original')
    init.emit(b'\x48\x81\xfb' + struct.pack('<I', SLOTS))
    init.relative(b'\x0f\x8c', 0x784380)
    init.relative(b'\xe9', 0x7843e3)
    init.label('original')
    init.emit(b'\x48\x83\xfb\x1b')
    init.relative(b'\x0f\x8c', 0x784380)
    init.relative(b'\xe9', 0x7843e3)

    update = Assembler(UPDATE_CAVE)
    update.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    update.emit(b'\x48\x39\x45\x00')
    update.branch(b'\x0f\x85', 'original')
    update.emit(b'\x41\x81\xfd' + struct.pack('<I', SLOTS))
    update.relative(b'\xe9', UPDATE_SITE + 7)
    update.label('original')
    update.emit(bytes.fromhex('4181fd87000000'))
    update.relative(b'\xe9', UPDATE_SITE + 7)

    opened = Assembler(OPEN_CAVE)
    opened.relative(b'\x48\x8d\x05', INVENTORY_VTABLE)
    opened.emit(b'\x48\x39\x01')
    opened.branch(b'\x0f\x85', 'original')
    opened.emit(b'\xc6\x81\xd8\x05\0\0\x01')
    opened.label('original')
    opened.relative(b'\xe9', 0x78af00)
    return init.finish(), update.finish(), opened.finish()


def patch_inventory_dll(payload):
    data = bytearray(payload)
    init, update, opened = inventory_code()
    edits = [
        (INIT_SITE, bytes.fromhex('4883fb1b7c9d'), b'\xe9' + struct.pack('<i', INIT_CAVE - INIT_SITE - 5) + b'\x90'),
        (UPDATE_SITE, bytes.fromhex('4181fd87000000'), b'\xe9' + struct.pack('<i', UPDATE_CAVE - UPDATE_SITE - 5) + b'\x90\x90'),
        (OPEN_SITE, bytes.fromhex('e8da610000'), b'\xe8' + struct.pack('<i', OPEN_CAVE - OPEN_SITE - 5)),
        (LAYOUT_SITE, bytes.fromhex('66450f2fc1'), b'\xe9' + struct.pack('<i', LAYOUT_CAVE - LAYOUT_SITE - 5)),
        (SCROLL_SITE, bytes.fromhex('ff9090060000'), b'\xe9' + struct.pack('<i', SCROLL_CAVE - SCROLL_SITE - 5) + b'\x90'),
    ]
    # Native out-of-range checks originally continue to the bounded loop tail.
    # Retain a finite cutoff and exit early at the actual vector length.
    for site, target, exit_target, cave in EFFECT_LOOPS:
        old = b'\x48\x83\xfd\x1b\x0f\x8c' + struct.pack('<i', target - site - 10)
        edits.append((site, old, b'\xe9' + struct.pack('<i', cave - site - 5) + b'\x90' * 5))
    for site, old_target, exit_target in [(0x788b5e, 0x788c96, 0x788ca8),
                                         (0x788d7f, 0x788e9d, 0x788eaf)]:
        expected = b'\x0f\x8d' + struct.pack('<i', old_target - site - 6)
        replacement = b'\x0f\x8d' + struct.pack('<i', exit_target - site - 6)
        edits.append((site, expected, replacement))
    for site, expected, replacement in edits:
        if data[site:site + len(expected)] != expected:
            raise ValueError(f'Unsupported inventory instruction at {site:x}')
        data[site:site + len(expected)] = replacement
    caves = [(INIT_CAVE, init), (UPDATE_CAVE, update), (OPEN_CAVE, opened),
             (LAYOUT_CAVE, layout_code()), (SCROLL_CAVE, scroll_code())]
    caves += [(cave, effect_loop_code(cave, target, exit_target))
              for _, target, exit_target, cave in EFFECT_LOOPS]
    for cave, code in caves:
        if len(code) > 0x80 or any(data[cave:cave + len(code)]):
            raise ValueError('Inventory hook does not fit the verified empty code region')
        data[cave:cave + len(code)] = code
    return bytes(data)


def patch_layout(root):
    root.set('frame', '680,90,560,684')
    root.set('flag', 'close;title;vresizable;')
    pages = root.findall(".//Widget[@type='tabpage']") or [root]
    for page in pages:
        if page is not root:
            page.set('frame', '0,24,558,561')
        nav = page.find("Widget[@name='inv_navi_container']")
        if nav is not None:
            page.remove(nav)
        container = page.find("Widget[@name='inv_container']")
        if container is None:
            raise ValueError('Inventory container is missing')
        container.set('frame', '2,3,556,559')
        viewport = container.find("Widget[@name='inv_scrollable']")
        viewport.set('frame', '1,1,540,558')
        for child in list(viewport):
            if child.get('name') not in ('button0', 'inv0'):
                viewport.remove(child)
        header = viewport.find("Widget[@name='button0']")
        header.set('frame', '0,0,0,0')
        # Native layout uses header visibility to decide whether the grid is visible.
        # An empty zero-height header keeps the native binding without cube chrome.
        header.set('flag', 'not_active;')
        header.attrib.pop('preset', None)
        for child in list(header):
            header.remove(child)
        grid = viewport.find("Widget[@name='inv0']")
        grid.set('frame', f'1,0,536,{GRID_HEIGHT}')
        grid.attrib.pop('preset', None)
        cells = grid.find("Widget[@name='list0']")
        cells.set('frame', f'2,2,532,{GRID_HEIGHT - 4}')
        cells.set('slot_num', str(SLOTS))
        scrollbar = container.find("Widget[@name='inv_scroll']")
        scrollbar.set('frame', '540,1,16,558')
        scrollbar.find("Widget[@name='plus']").set('frame', '0,545,16,12')
    for tabs in root.findall("Widget[@type='tabsheet']"):
        tabs.set('frame', '-2,1,558,585')
        tabs.find("Widget[@type='tab']").set('frame', '0,0,558,25')
    expand = root.find("Widget[@name='expand']")
    if expand is not None:
        root.remove(expand)
    bottom = root.find("Widget[@name='bottom']")
    bottom.set('frame', '0,590,556,30')
    bottom.set('v_pos_align', 'bottom')
    for widget in bottom:
        name = widget.get('name')
        if name in ('trashcan', 'inv_temp', 'slot_count', 'money', 'money_item', 'sort', 'inv_to_toypet', 'inv_to_coin'):
            x, _, w, h = map(int, widget.get('frame').split(','))
            y = {'trashcan': 4, 'inv_temp': 6, 'slot_count': 6, 'money': 5,
                 'money_item': 6, 'sort': 7, 'inv_to_toypet': 6, 'inv_to_coin': 4}[name]
            widget.set('frame', f'{x},{y},{w},{h}')
        if name == 'slot_count':
            widget.set('frame', '56,6,105,18')
        elif name in ('money', 'money_item', 'sort', 'inv_to_toypet', 'inv_to_coin'):
            # Absolute native positions make rebuilding an installed layout idempotent.
            x = {'money': 332, 'money_item': 333, 'sort': 537,
                 'inv_to_toypet': 306, 'inv_to_coin': 300}[name]
            _, y, w, h = map(int, widget.get('frame').split(','))
            widget.set('frame', f'{x},{y},{w},{h}')
    from inventory_search import patch_search_layout
    return patch_search_layout(root)
