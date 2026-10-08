"""Execute patched native loop control with slot-effect calls replaced by counters."""
import ctypes
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from patch_game_dll import Assembler
from unified_inventory import SLOTS

dll = Path(sys.argv[1]).read_bytes()
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
k.VirtualAlloc.restype = ctypes.c_void_p
k.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
k.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
size = 0x1450000
base = k.VirtualAlloc(None, size, 0x3000, 4)
assert base
def put(off, code):
    ctypes.memmove(base + off, code, len(code))

try:
    for start, end in [(0x788ad0, 0x788cee), (0x788cf0, 0x788eee), (0x144de80, 0x144df80)]:
        put(start, dll[start:end])
    # Keep the real vector guards, loop indices, patched bounds and outer loops.
    # Replace only item effect work, which calls unrelated game services.
    for read, continuation, cave in [(0x788b64, 0x788c96, 0x2000), (0x788d85, 0x788e9d, 0x2100)]:
        counter = Assembler(cave)
        counter.relative(b'\x48\xff\x05', 0x1000)
        counter.relative(b'\xe9', continuation)
        put(cave, counter.finish())
        put(read, b'\xe9' + struct.pack('<i', cave - read - 5) + b'\x90\x90')
    old = ctypes.c_uint32()
    assert k.VirtualProtect(base, size, 0x40, ctypes.byref(old))
    for entry in [0x788ad0, 0x788cf0]:
        fn = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(base + entry)
        for length in [0, 1, 26, 27, 135, 179, 180, SLOTS - 1, SLOTS, SLOTS + 20]:
            dialog = ctypes.create_string_buffer(0x650)
            lists = []
            expected = 0
            for group, count in enumerate([length, 27, 0, 1, None]):
                if count is None:
                    continue
                view = ctypes.create_string_buffer(0x3c8)
                vector = (ctypes.c_uint64 * max(count, 1))()
                first = ctypes.addressof(vector)
                struct.pack_into('<QQ', view, 0x3b8, first, first + count * 8)
                struct.pack_into('<Q', dialog, 0x588 + group * 8, ctypes.addressof(view))
                dialog[0x5dd + group] = b'\x01'
                lists += [view, vector]
                expected += min(count, SLOTS)
            ctypes.c_uint64.from_address(base + 0x1000).value = 0
            fn(dialog)
            actual = ctypes.c_uint64.from_address(base + 0x1000).value
            assert actual == expected, (hex(entry), length, actual, expected)
    print(f'PASS: both native effect loops terminate at vector length or {SLOTS} slots; empty and missing groups exit safely.')
finally:
    k.VirtualFree(base, 0, 0x8000)
