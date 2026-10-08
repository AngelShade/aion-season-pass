"""Execute the scroll refresh hook and native thumb clamp with isolated widgets."""
import ctypes
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unified_inventory as u
from patch_game_dll import Assembler

k = ctypes.WinDLL('kernel32', use_last_error=True)
k.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
k.VirtualAlloc.restype = ctypes.c_void_p
k.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
k.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
size = 0x1450000
base = k.VirtualAlloc(None, size, 0x3000, 4)
assert base

def put(offset, code):
    ctypes.memmove(base + offset, code, len(code))

try:
    dll = Path(sys.argv[1]).read_bytes()
    put(u.SCROLL_CAVE, dll[u.SCROLL_CAVE:u.SCROLL_CAVE + 0x80])
    # Use the real native float conversion, 0..1 clamp, and thumb write.
    put(0x7897f8, dll[0x7897f8:0x78985a])
    put(0x78985a, b'\xc3')
    put(0x543b50, b'\xc3')
    put(u.SCROLL_SITE + 6, b'\xc3')
    other_vtable = u.INVENTORY_VTABLE + 0x800
    put(other_vtable + 0x690, struct.pack('<Q', base + 0x2000))
    put(0x2000, bytes.fromhex('ff811006000031c0c3'))
    one_rva = 0x789841 + struct.unpack_from('<i', dll, 0x78983d)[0]
    put(one_rva, struct.pack('<f', 1.0))
    # The native routine restores xmm10 from its existing stack spill.
    asm = Assembler(0x1000)
    asm.emit(bytes.fromhex('5341574154574881ec080500004989cc4889d74d89c7'))
    for index, reg in enumerate([6, 9, 10, 11, 14]):
        # movdqu [rsp+offset], xmmN
        rex = b'\x44' if reg >= 8 else b''
        asm.emit(b'\xf3' + rex + b'\x0f\x7f' + bytes([0x84 | ((reg & 7) << 3), 0x24]) + struct.pack('<I', 0x400 + index * 16))
    asm.emit(bytes.fromhex('f2440f109900060000f3450f5a973404000066450fefe4b301'))
    asm.emit(bytes.fromhex('4883ec08'))  # Match the original layout routine's aligned stack.
    asm.relative(b'\xe8', u.SCROLL_CAVE)
    asm.emit(bytes.fromhex('4883c408'))
    for index, reg in enumerate([6, 9, 10, 11, 14]):
        rex = b'\x44' if reg >= 8 else b''
        asm.emit(b'\xf3' + rex + b'\x0f\x6f' + bytes([0x84 | ((reg & 7) << 3), 0x24]) + struct.pack('<I', 0x400 + index * 16))
    asm.emit(bytes.fromhex('4881c4080500005f415c415f5bc3'))
    put(0x1000, asm.finish())
    old = ctypes.c_uint32()
    assert k.VirtualProtect(base, size, 0x20, ctypes.byref(old))
    fn = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(base + 0x1000)
    dialog = ctypes.create_string_buffer(0x650)
    viewport = ctypes.create_string_buffer(0x400)
    bar = ctypes.create_string_buffer(0x480)
    struct.pack_into('<Q', dialog, 0, base + u.INVENTORY_VTABLE)
    for scale in [1.0, 1.125, 1.5]:
        struct.pack_into('<d', dialog, 0x600, u.GRID_HEIGHT * scale)
        for position in [0.0, 0.25, 0.5, 1.0]:
            struct.pack_into('<d', viewport, 0x88, 392 * scale)
            struct.pack_into('<f', bar, 0x434, position)
            fn(dialog, viewport, bar)
            actual = struct.unpack_from('<f', bar, 0x434)[0]
            assert abs(actual - position) < 1e-6, (scale, position, actual)
    struct.pack_into('<Q', dialog, 0, base + other_vtable)
    struct.pack_into('<I', dialog, 0x610, 0)
    struct.pack_into('<f', bar, 0x434, 0.5)
    fn(dialog, viewport, bar)
    assert struct.unpack_from('<I', dialog, 0x610)[0] == 1
    assert struct.unpack_from('<f', bar, 0x434)[0] == 0.5
    print('PASS: native refresh retains scroll position; other dialogs use their original callback.')
finally:
    k.VirtualFree(base, 0, 0x8000)
