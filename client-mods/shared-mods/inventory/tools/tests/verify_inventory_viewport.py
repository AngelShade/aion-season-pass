"""Isolated execution of native viewport clamp, UI scale and scrollbar gating."""
import ctypes, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unified_inventory as u
from patch_game_dll import Assembler
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32];k.VirtualAlloc.restype=ctypes.c_void_p
k.VirtualProtect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)]
k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
size=0x1450000;base=k.VirtualAlloc(None,size,0x3000,4);assert base
def put(off,code):ctypes.memmove(base+off,code,len(code))
try:
 dll=Path(sys.argv[1]).read_bytes()
 put(u.LAYOUT_CAVE,dll[u.LAYOUT_CAVE:u.LAYOUT_CAVE+0x80])
 put(0x78952d,b'\xc3');put(u.LAYOUT_SITE+5,b'\xc3')
 asm=Assembler(0x1000)
 asm.emit(bytes.fromhex('535541544883ec504989ccf3440f7f642420f3440f7f4c2430'))
 asm.emit(bytes.fromhex('f2440f10e2f2440f10cb31db'))  # total xmm2 -> xmm12, grid height xmm3 -> xmm9
 asm.relative(b'\xe8',u.LAYOUT_CAVE)
 asm.emit(bytes.fromhex('f2440f1122885a08f3440f6f642420f3440f6f4c24304883c450415c5d5bc3'))
 put(0x1000,asm.finish())
 old=ctypes.c_uint32();assert k.VirtualProtect(base,size,0x20,ctypes.byref(old))
 fn=ctypes.CFUNCTYPE(None,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_double,ctypes.c_double)(base+0x1000)
 dialog=ctypes.create_string_buffer(0x650);out=ctypes.create_string_buffer(16)
 for normal in [True,False]:
  struct.pack_into('<Q',dialog,0,base+u.INVENTORY_VTABLE+(0 if normal else 8))
  for scale in [1.0,1.125,1.5]:
   for total in [0,100,391,392,650,u.GRID_HEIGHT]:
    fn(dialog,out,total*scale,u.GRID_HEIGHT*scale)
    actual=struct.unpack_from('<d',out)[0];scroll=out.raw[8]
    expected=min(total,u.VISIBLE_GRID_HEIGHT)*scale if normal else total*scale
    assert abs(actual-expected)<1e-8,(normal,scale,total,actual,expected)
    assert scroll==int(normal and total>u.VISIBLE_GRID_HEIGHT),(normal,scale,total,scroll)
 print('PASS: nine-row native viewport, UI scaling, scrollbar range, and original behavior for other inventory dialogs.')
finally:k.VirtualFree(base,0,0x8000)
