"""Open the normal inventory independently beside Warehouse and Profile (4.8 NA)."""
import struct
from patch_game_dll import Assembler

OWNER_LIST = 0xed9088
OWNER_IDS = (180, 181, 247, 265, 264, 208, 300, 301, 304, 305, 349, 352, 30)
DOCK_ROUTINE = 0x78b730
OPEN_CALLS = (0x947acd, 0x833cb0)
# Verified executable padding immediately before the menu command hook.
OPEN_CAVE = 0x144d080
OPEN_REGION_SIZE = 0x80
NORMAL_INVENTORY = 0x13875c0 + 0x1b * 8
WAREHOUSE_CLOSE_SITE = 0x947d35
WAREHOUSE_CLOSE_END = 0x947d63


def open_code():
    a = Assembler(OPEN_CAVE)
    a.emit(bytes.fromhex('4883ec28'))
    # Preserve the stock reconciliation for other dialogs. Both OnVisible
    # callers already retain their show/hide argument in nonvolatile r12d.
    a.relative(b'\xe8', DOCK_ROUTINE)
    a.emit(bytes.fromhex('4585e4'))
    a.branch(b'\x0f\x84', 'done')
    a.relative(bytes.fromhex('488b0d'), NORMAL_INVENTORY)
    a.emit(bytes.fromhex('4885c9'))
    a.branch(b'\x0f\x84', 'done')
    # Native Show rather than Toggle keeps an already-open inventory visible
    # and retains its rectangle, resize state, search and scroll position.
    a.emit(bytes.fromhex('488b01ba010000004531c0ff90d0000000'))
    a.label('done')
    a.emit(bytes.fromhex('4883c428c3'))
    return a.finish()


def edits():
    result = []
    for index in (2, 12):
        result.append((OWNER_LIST + index * 4, struct.pack('<I', OWNER_IDS[index]), b'\xff' * 4))
    for site in OPEN_CALLS:
        result.append((site, b'\xe8' + struct.pack('<i', DOCK_ROUTINE-site-5),
                       b'\xe8' + struct.pack('<i', OPEN_CAVE-site-5)))
    # Warehouse's hide handler normally closes the ordinary inventory as well.
    # Retain every warehouse save/cleanup operation and skip only that block.
    result.append((WAREHOUSE_CLOSE_SITE, bytes.fromhex('488b1d5cf9a300'),
                   b'\xe9' + struct.pack('<i', WAREHOUSE_CLOSE_END-WAREHOUSE_CLOSE_SITE-5) + b'\x90\x90'))
    return result


def patch_detached_inventory(payload):
    data = bytearray(payload)
    changes = edits()
    code = open_code()
    if len(code) > OPEN_REGION_SIZE:
        raise ValueError('Detached inventory hook exceeds its reserved region')
    already = all(data[p:p+len(new)] == new for p, _, new in changes)
    if already:
        if data[OPEN_CAVE:OPEN_CAVE+len(code)] != code:
            raise ValueError('Detached inventory hook changed')
        return bytes(data)
    if tuple(struct.unpack_from('<13I', data, OWNER_LIST)) != OWNER_IDS:
        raise ValueError('Unsupported native inventory owner list')
    if any(data[OPEN_CAVE:OPEN_CAVE+OPEN_REGION_SIZE]):
        raise ValueError('Detached inventory code region is occupied')
    for position, old, new in changes:
        if data[position:position+len(old)] != old:
            raise ValueError(f'Unsupported detached inventory instruction at {position:x}')
        data[position:position+len(old)] = new
    data[OPEN_CAVE:OPEN_CAVE+len(code)] = code
    return bytes(data)
