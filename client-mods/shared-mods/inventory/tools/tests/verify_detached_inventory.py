"""Execute the detached-inventory opening hook with native widget fixtures."""
import ctypes as c
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detached_inventory as p
from patch_game_dll import Assembler

dll = Path(sys.argv[1]).read_bytes()
for site, old, new in p.edits():
    assert dll[site:site+len(new)] == new, hex(site)
owners = struct.unpack_from('<13I', dll, p.OWNER_LIST)
assert owners == tuple(0xffffffff if i in (2,12) else value for i,value in enumerate(p.OWNER_IDS))
assert p.patch_detached_inventory(dll) == dll, 'Reapplying must be idempotent'
k = c.WinDLL('kernel32', use_last_error=True)
k.VirtualAlloc.argtypes=[c.c_void_p,c.c_size_t,c.c_uint32,c.c_uint32]; k.VirtualAlloc.restype=c.c_void_p
k.VirtualProtect.argtypes=[c.c_void_p,c.c_size_t,c.c_uint32,c.POINTER(c.c_uint32)]
k.VirtualFree.argtypes=[c.c_void_p,c.c_size_t,c.c_uint32]
size=0x1450000; base=k.VirtualAlloc(None,size,0x3000,4); assert base
def put(offset, data): c.memmove(base+offset,data,len(data))
try:
    put(p.OPEN_CAVE,p.open_code())
    # Original docking routine increments its call counter and returns.
    a=Assembler(p.DOCK_ROUTINE);a.relative(bytes.fromhex('ff05'),0x2000);a.emit(b'\xc3');put(a.base,a.finish())
    # Mock native Show checks arguments and records visibility, leaving rectangle
    # and all item/search/scroll state untouched.
    put(0x3000,bytes.fromhex('89910001000044898104010000ff8108010000c3'))
    widget=c.create_string_buffer(0x650); vtable=c.create_string_buffer(0x700)
    struct.pack_into('<Q',widget,0,c.addressof(vtable));struct.pack_into('<Q',vtable,0xd0,base+0x3000)
    rectangle=struct.pack('<4d',411,93,560,684);c.memmove(c.addressof(widget)+0x50,rectangle,len(rectangle))
    # Callers retain visibility in r12d. Verify it survives the emitted hook.
    a=Assembler(0x1000);a.emit(bytes.fromhex('41544883ec204189cc'))
    a.relative(b'\xe8',p.OPEN_CAVE);a.emit(bytes.fromhex('4489e04883c420415cc3'));put(a.base,a.finish())
    old=c.c_uint32();assert k.VirtualProtect(base,size,0x40,c.byref(old))
    fn=c.CFUNCTYPE(c.c_int,c.c_int)(base+0x1000)
    for available in [False,True]:
        put(p.NORMAL_INVENTORY,struct.pack('<Q',c.addressof(widget) if available else 0))
        for shown in [0,1,1,0]:
            before=struct.unpack_from('<I',widget,0x108)[0]
            assert fn(shown)==shown, 'Caller visibility register corrupted'
            after=struct.unpack_from('<I',widget,0x108)[0]
            assert after-before==int(available and shown), (available,shown)
            assert widget.raw[0x50:0x70]==rectangle, 'Inventory dragged position changed'
            if available and shown:
                assert struct.unpack_from('<II',widget,0x100)==(1,0), 'Wrong native Show flags'
    assert c.c_uint32.from_address(base+0x2000).value==8
    print('PASS: Warehouse/Profile open the normal inventory; hide does not close it; repeated opens preserve its rectangle; null widgets and r12 state handled; other docking owners preserved.')
finally:
    k.VirtualFree(base,0,0x8000)
