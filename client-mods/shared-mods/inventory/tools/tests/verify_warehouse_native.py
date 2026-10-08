"""Execute warehouse search and initialization hooks in isolated native fixtures."""
import ctypes as c
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inventory_search as inv
import warehouse_search as wh
import warehouse_patch as capacity

dll = Path(sys.argv[1]).read_bytes()
k = c.WinDLL('kernel32', use_last_error=True)
k.VirtualAlloc.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.c_uint32]
k.VirtualAlloc.restype = c.c_void_p
k.VirtualProtect.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32, c.POINTER(c.c_uint32)]
k.VirtualFree.argtypes = [c.c_void_p, c.c_size_t, c.c_uint32]
size = 0x1450000
base = k.VirtualAlloc(None, size, 0x3000, 4)
assert base
callbacks, objects = [], []


def put(offset, value):
    c.memmove(base + offset, value, len(value))


def obj(length=0x700):
    result = c.create_string_buffer(length)
    objects.append(result)
    return result


def addr(value):
    return c.addressof(value)


def callback(signature, fn):
    value = signature(fn)
    callbacks.append(value)
    return c.cast(value, c.c_void_p).value


try:
    put(wh.CODE, dll[wh.CODE:wh.END])
    put(inv.MATCH, dll[inv.MATCH:inv.MATCH + 0x100])
    vt, dialog = obj(), obj()
    struct.pack_into('<Q', dialog, 0, addr(vt))
    queries = [c.create_unicode_buffer('', 64), c.create_unicode_buffer('', 64)]
    edits = [obj(), obj()]
    buttons = [obj() for _ in range(4)]
    widgets = dict(zip(wh.NAMES[:4], buttons))
    widgets.update(dict(zip(wh.NAMES[4:], edits)))
    bindings, cells, lists, vectors = {}, [], [], []
    for index, limit in enumerate([wh.CHARACTER_SLOTS, wh.ACCOUNT_SLOTS]):
        view = obj()
        vector = (c.c_void_p * limit)()
        vectors.append(vector)
        lists.append(view)
        struct.pack_into('<Q', dialog, 0x540 + index * 8, addr(view))
        struct.pack_into('<QQ', view, 0x3b8, addr(vector), addr(vector) + limit * 8)
        panel_cells = []
        for slot in range(limit):
            cell = obj(0x180)
            struct.pack_into('<Q', cell, 0, addr(view))
            struct.pack_into('<III', cell, 0x90, slot, 0, 1 + index)
            vector[slot] = addr(cell)
            panel_cells.append(cell)
        cells.append(panel_cells)
        for slot, name in [(0, 'Kinah'), (limit - 1, 'Potion')]:
            item = obj()
            item[0x20:0x20 + (len(name) + 1) * 2] = (name + '\0').encode('utf-16le')
            struct.pack_into('<Q', item, 0x38, 7)
            ident = 1000 + index * 1000 + slot
            bindings[ident] = addr(item)
            struct.pack_into('<I', panel_cells[slot], 0x94, ident)
        struct.pack_into('<Q', edits[index], 0, addr(vt))
    def lookup(owner, name, *unused):
        return addr(widgets[c.string_at(name).decode()])
    def get_text(widget):
        return addr(queries[0 if widget == addr(edits[0]) else 1])
    def set_text(widget, text):
        queries[0 if widget == addr(edits[0]) else 1].value = c.wstring_at(text)
    for offset, pointer in [
        (0x338, callback(c.CFUNCTYPE(c.c_uint64, c.c_void_p, c.c_void_p, c.c_uint32), lookup)),
        (0x340, callback(c.CFUNCTYPE(c.c_uint64, c.c_void_p, c.c_void_p), lookup)),
        (0x298, callback(c.CFUNCTYPE(c.c_uint64, c.c_void_p), get_text)),
        (0x290, callback(c.CFUNCTYPE(None, c.c_void_p, c.c_void_p), set_text)),
    ]:
        struct.pack_into('<Q', vt, offset, pointer)
    item_fn = callback(c.CFUNCTYPE(c.c_uint64, c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32),
                       lambda game, storage, ident, unused: bindings.get(ident, 0))
    put(0x444030, b'\x48\xb8' + struct.pack('<Q', item_fn) + b'\xff\xe0')
    put(0x12eda48, struct.pack('<Q', addr(dialog)))
    dispatch = wh.CODE
    while dll[dispatch:dispatch + 8] != bytes.fromhex('53564883ec284889'):
        dispatch += 16
        assert dispatch < wh.STATE_CHARACTER
    event = (c.c_void_p * 1)()
    # Also execute the real enlarged initialization comparisons at their boundaries.
    put(capacity.CAVE, dll[capacity.CAVE:capacity.CAVE + 0x180])
    wrappers = []
    for index, (site, displaced) in enumerate(capacity.HOOKS[:2]):
        target = site + 5 + struct.unpack_from('<i', dll, site + 1)[0]
        loop = 0x946e90 if index == 0 else 0x946f30
        put(loop, bytes.fromhex('b801000000c3'))
        put(site + len(displaced), bytes.fromhex('31c0c3'))
        offset = 0x1000 + index * 0x100
        a = wh.Assembler(offset)
        a.emit(bytes.fromhex('574889cf4883ec20'))
        a.relative(b'\xe8', target)
        a.emit(bytes.fromhex('4883c4205fc3'))
        put(offset, a.finish())
        wrappers.append(offset)
    old = c.c_uint32()
    assert k.VirtualProtect(base, size, 0x40, c.byref(old))
    click = c.CFUNCTYPE(c.c_uint32, c.c_void_p, c.c_void_p)(base + dispatch)
    states = [(c.c_ubyte * 0x400).from_address(base + s) for s in [wh.STATE_CHARACTER, wh.STATE_ACCOUNT]]
    for index, limit in enumerate([360, 540]):
        queries[index].value = 'pOtIoN'
        event[0] = addr(buttons[index * 2])
        assert click(addr(dialog), event) == 1
        assert states[index][8] == 1 and states[index][0x20 + limit - 1] == 1
        assert states[index][0x20] == 0
    assert states[0][0x20 + 359] == 1 and states[1][0x20 + 539] == 1
    event[0] = addr(buttons[1])
    assert click(addr(dialog), event) == 1 and queries[0].value == '' and states[0][8] == 0
    assert queries[1].value == 'pOtIoN' and states[1][8] == 1, 'Clear remains independent'
    # Short vectors, null cells and unknown item IDs are safe.
    vectors[1][0] = None
    struct.pack_into('<Q', lists[1], 0x3c0, addr(vectors[1]) + 2 * 8)
    event[0] = addr(buttons[2])
    assert click(addr(dialog), event) == 1 and not any(states[1][0x20:0x20 + 540])
    event[0] = addr(obj())
    assert click(addr(dialog), event) == 0, 'Unhandled buttons remain native'
    for offset, limit in zip(wrappers, [360, 540]):
        compare = c.CFUNCTYPE(c.c_uint32, c.c_uint64)(base + offset)
        for slot in [0, limit - 1, limit, limit + 1]:
            assert compare(slot) == int(slot < limit)
    print('PASS: independent warehouse Search/Clear, final-slot matches, short/null vectors, other buttons and exact 360/540 native bounds.')
finally:
    k.VirtualFree(base, 0, 0x8000)
