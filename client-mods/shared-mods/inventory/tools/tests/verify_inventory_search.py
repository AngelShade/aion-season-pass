"""Execute search machine code with isolated widgets and item bindings.

Native widget lookup, item lookup, text access, and layout are controlled ABI
fixtures. No game process, files in the client, packets, or database are touched.
"""
import ctypes
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inventory_search as s
from patch_game_dll import Assembler

k = ctypes.WinDLL('kernel32', use_last_error=True)
k.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
k.VirtualAlloc.restype = ctypes.c_void_p
k.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
k.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
base = k.VirtualAlloc(None, 0x1450000, 0x3000, 4)
assert base


def put(rva, data):
    ctypes.memmove(base + rva, data, len(data))


def obj(size=0x700):
    value = ctypes.create_string_buffer(size)
    struct.pack_into('<Q', value, 0, base + s.INVENTORY_VTABLE)
    return value


def addr(value):
    return ctypes.addressof(value)


try:
    dll = Path(sys.argv[1]).read_bytes()
    put(s.MATCH, dll[s.MATCH:s.MATCH + 0x100])
    put(s.POLL, dll[s.POLL:s.POLL + 0x700])
    put(s.BUTTON, dll[s.BUTTON:s.BUTTON + 0x200])
    put(s.DRAW, dll[s.DRAW:s.DRAW + 0x100])
    put(s.STRINGS, dll[s.STRINGS:s.STRINGS + 0x100])
    state = (ctypes.c_char * 0x200).from_address(base + s.STATE)
    dialog, edit, status, bar, clear, view, viewport, grid = [obj() for _ in range(8)]
    bindings, names, items, cells = {}, [], [], []
    vector = (ctypes.c_void_p * s.SLOTS)()
    query = ctypes.create_unicode_buffer('', 64)
    status_values, layout_calls, failures = [], [], []
    widgets = {'inventory_search': edit, 'inventory_search_count': status,
               'inventory_search_clear': clear,
               'inv_scroll': bar, 'inv_scrollable': viewport}
    kinds = {'inventory_search': 0x200b, 'inventory_search_count': 0x2022,
             'inventory_search_clear': 0x2001,
             'inv_scroll': 0x201e, 'inv_scrollable': 0x201d}
    callbacks = []

    def callback(signature, fn):
        wrapped = signature(fn)
        callbacks.append(wrapped)
        return ctypes.cast(wrapped, ctypes.c_void_p).value

    def widget_lookup(owner, name, kind):
        name = ctypes.string_at(name).decode()
        if kind != kinds.get(name):
            failures.append(('wrong native widget type', name, kind))
            return 0
        return addr(widgets[name])

    def set_text(widget, text):
        value = ctypes.wstring_at(text)
        if widget == addr(edit):
            query.value = value
        elif widget == addr(status):
            status_values.append(value)
        else:
            failures.append(('unexpected text target', widget))

    def item_lookup(game, storage, object_id, unused):
        if storage != 1:
            failures.append(('wrong storage type', storage))
        return bindings.get(object_id, 0)

    def layout(owner, animate):
        layout_calls.append(struct.unpack_from('<f', bar, 0x434)[0])
        return 1

    vt = s.INVENTORY_VTABLE
    for offset, pointer in [
        (0x338, callback(ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32), widget_lookup)),
        (0x298, callback(ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p), lambda widget: addr(query))),
        (0x290, callback(ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p), set_text)),
        (0x698, callback(ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32), layout)),
    ]:
        put(vt + offset, struct.pack('<Q', pointer))
    item_fn = callback(ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32), item_lookup)
    put(0x444030, b'\x48\xb8' + struct.pack('<Q', item_fn) + b'\xff\xe0')
    put(0x12eda48, struct.pack('<Q', addr(dialog)))
    struct.pack_into('<Q', dialog, 0x588, addr(view))
    struct.pack_into('<Q', dialog, 0x5b0, addr(grid))
    struct.pack_into('<d', grid, 0x68, s.GRID_HEIGHT)
    struct.pack_into('<d', viewport, 0x88, s.VISIBLE_GRID_HEIGHT)
    struct.pack_into('<QQ', view, 0x3b8, addr(vector), addr(vector) + s.SLOTS * 8)
    for i in range(s.SLOTS):
        cell = obj(0x180)
        struct.pack_into('<Q', cell, 0, addr(view))
        struct.pack_into('<III', cell, 0x90, i, 0, 1)
        cells.append(cell)
        vector[i] = addr(cell)

    def add_item(slot, object_id, name):
        item = obj()
        if len(name) < 8:
            item[0x20:0x20 + (len(name) + 1) * 2] = (name + '\0').encode('utf-16le')
            struct.pack_into('<Q', item, 0x38, 7)
        else:
            text = ctypes.create_unicode_buffer(name)
            names.append(text)
            struct.pack_into('<Q', item, 0x20, addr(text))
            struct.pack_into('<Q', item, 0x38, len(name))
        items.append(item)
        bindings[object_id] = addr(item)
        struct.pack_into('<I', cells[slot], 0x94, object_id)

    add_item(2, 1001, 'Kinah')
    add_item(111, 1002, 'Greater Healing Potion')
    add_item(278, 1003, 'Fine Healing Potion')
    add_item(179, 1004, 'Ancient Sword')
    # Unhandled buttons must replay the displaced prologue and native callback.
    put(s.BUTTON_SITE + 10, bytes.fromhex('4881c498040000b807000000c3'))
    put(s.DRAW_SITE + 9, b'\xc3')
    a = Assembler(0x1000)
    a.emit(bytes.fromhex('534881ec400100004889cb'))
    for index, reg in enumerate((10, 11, 12)):
        a.emit(b'\xf3\x44\x0f\x7f' + bytes([0x84 | ((reg & 7) << 3), 0x24]) + struct.pack('<I', 0xe0 + index * 16))
        a.emit(b'\xf3\x44\x0f\x10' + bytes([((reg & 7) << 3) | 0x42, index * 4]))
    a.relative(b'\xe8', s.DRAW)
    for index, reg in enumerate((10, 11, 12)):
        a.emit(b'\xf3\x44\x0f\x11' + bytes([0x42 | ((reg & 7) << 3), index * 4]))
        a.emit(b'\xf3\x44\x0f\x6f' + bytes([0x84 | ((reg & 7) << 3), 0x24]) + struct.pack('<I', 0xe0 + index * 16))
    a.emit(bytes.fromhex('4881c4400100005bc3'))
    put(0x1000, a.finish())
    old = ctypes.c_uint32()
    assert k.VirtualProtect(base, 0x1450000, 0x40, ctypes.byref(old))
    match = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p)(base + s.MATCH)
    poll = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(base + s.POLL)
    button = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p)(base + s.BUTTON)
    draw = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(base + 0x1000)
    for name, term, wanted in [
        ('Greater Healing Potion', 'heALing', 1), ('Greater Healing Potion', 'sword', 0),
        ('Kinah', 'KI', 1), ('Élite Sword', 'Élite', 1), ('Short', 'Shorter', 0),
        ('Potion', 'ion', 1), ('A' * 512, 'B', 0), ('A' * 512, 'a' * 63, 1),
    ]:
        assert match(name, term) == wanted, (name[:30], term, wanted)
    poll(addr(dialog))
    assert not layout_calls and status_values == ['']
    struct.pack_into('<f', bar, 0x434, 0.4)
    query.value = 'heALing'
    poll(addr(dialog))
    assert state[s.FLAGS + 111] == b'\1' and state[s.FLAGS + 278] == b'\1'
    assert state[s.FLAGS + 2] == b'\0'
    assert status_values[-1] == '2 matches', status_values
    assert abs(layout_calls[-1] - (111 // 12 * 43 / 645)) < 1e-6
    assert len(layout_calls) == 1
    poll(addr(dialog))
    assert len(layout_calls) == 1, 'Normal refresh must retain manual scrolling'
    event = (ctypes.c_void_p * 1)(addr(clear))
    # Item movement changes presentation only; native object and slot IDs remain.
    struct.pack_into('<I', cells[278], 0x94, 0)
    struct.pack_into('<I', cells[200], 0x94, 1003)
    previous = len(layout_calls)
    poll(addr(dialog))
    assert state[s.FLAGS + 278] == b'\0' and state[s.FLAGS + 200] == b'\1'
    assert len(layout_calls) == previous
    colors = (ctypes.c_float * 3)(1, 1, 1)
    draw(addr(cells[2]), colors)
    assert all(abs(v - 0.28) < 1e-6 for v in colors), list(colors)
    colors[:] = [1, 1, 1]
    draw(addr(cells[111]), colors)
    assert list(colors) == [1, 1, 1]
    colors[:] = [1, 1, 1]
    other_cell = obj(0x180)
    draw(addr(other_cell), colors)
    assert list(colors) == [1, 1, 1], 'Other item views remain unchanged'
    query.value = 'not in inventory'
    poll(addr(dialog))
    assert status_values[-1] == 'No matches'
    event[0] = addr(clear)
    assert button(addr(dialog), event) == 1
    poll(addr(dialog))
    assert query.value == '' and status_values[-1] == ''
    assert abs(layout_calls[-1] - 0.4) < 1e-6, 'Clear restores pre-search scroll'
    colors[:] = [1, 1, 1]
    draw(addr(cells[2]), colors)
    assert list(colors) == [1, 1, 1]
    event[0] = addr(bar)
    assert button(addr(dialog), event) == 7, 'Unhandled native button preserved'
    query.value = 'Ki'
    # Short vectors, null cells, and missing object bindings cannot read past bounds.
    struct.pack_into('<Q', view, 0x3c0, addr(vector) + 3 * 8)
    vector[0] = None
    poll(addr(dialog))
    assert status_values[-1] == '1 matches'
    # Window resize and UI scale use the native current height, not a fixed ratio.
    struct.pack_into('<Q', view, 0x3c0, addr(vector) + s.SLOTS * 8)
    for scale, visible in [(1.0, 392), (1.125, 392), (1.5, 300)]:
        struct.pack_into('<d', grid, 0x68, s.GRID_HEIGHT * scale)
        struct.pack_into('<d', viewport, 0x88, visible * scale)
        query.value = 'Sword'
        poll(addr(dialog))
        assert abs(layout_calls[-1] - min(1, 179 // 12 * 43 / (s.GRID_HEIGHT - visible))) < 1e-6
        query.value = 'Ki'
        poll(addr(dialog))
    # Three-digit match counts remain readable and do not overflow the text buffer.
    for slot in range(100):
        add_item(slot, 2000 + slot, 'Healing Potion')
        vector[slot] = addr(cells[slot])
    query.value = 'potion'
    poll(addr(dialog))
    assert status_values[-1] == '102 matches', status_values[-1]
    assert not failures, failures
    assert struct.unpack_from('<I', cells[200], 0x90)[0] == 200
    assert struct.unpack_from('<I', cells[200], 0x94)[0] == 1003
    print('PASS: name matching, native ABI, live count, clear/scroll restore, moved items, bounds, dimming, and other widgets.')
finally:
    k.VirtualFree(base, 0, 0x8000)
