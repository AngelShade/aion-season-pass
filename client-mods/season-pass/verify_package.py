"""Verify the staged native patch, preserved archives, signatures and recovery guards."""
import argparse
import json
import sys
import subprocess
from pathlib import Path
from prepare import sha, read_pak, patch, menu, AUTH, BROWSER, NEW_AUTH, NEW_BROWSER
from verify_shortcut import verify as verify_shortcut

def verify(out):
    m=json.loads((out/'manifest.json').read_text(encoding='utf-8-sig')); root=Path(m['clientRoot'])
    assert m['feature']=='daeva-season-pass'
    assert sha((root/'Pub.key').read_bytes())==m['sourceKey']=='11c64ff8e5dde91b281b57ac2b372dc0c8f0df0df9e18c936335d10e63d85136'
    for e in m['files']:
        assert sha((out/e['path']).read_bytes())==e['installed'],e['path']
        assert sha((root/e['path']).read_bytes())==e['original'],e['path']
    for e in m['preservedFiles']:assert sha((root/e['path']).read_bytes())==e['sha256'],e['path']
    assert patch((root/'bin64/Game.dll').read_bytes())==(out/'bin64/Game.dll').read_bytes()
    original=(root/'bin64/Game.dll').read_bytes(); result=(out/'bin64/Game.dll').read_bytes(); offset=0
    for start,end in sorted(m['allowedDllRanges']):
        assert original[offset:start]==result[offset:start],hex(offset)
        offset=end
    assert original[offset:]==result[offset:] and len(original)==len(result)
    source=read_pak(root/'Plugin/RelicCalc/RelicCalc.pak'); staged=read_pak(out/'Plugin/RelicCalc/RelicCalc.pak')
    assert source.namelist()==staged.namelist() and staged.testzip() is None
    for name in source.namelist():assert staged.read(name)==(menu(source.read(name)) if name=='PrivateMenus.lua' else source.read(name)),name
    verify_shortcut(root,out)
    subprocess.run(['java',str(Path(__file__).with_name('VerifySignatures.java')),str(out),str(root)],check=True)
    state=json.loads((out/'DXVK/graphics-menu/installed.json').read_text())
    package=json.loads((out/'DXVK/graphics-menu/package/manifest.json').read_text()); assert state['files']==package['files']
    for e in state['files']:
        rel=e['path']; data=(out/rel if (out/rel).exists() else root/rel).read_bytes(); assert sha(data)==e['installed'],rel
    assert len(NEW_AUTH)<=512 and len(NEW_BROWSER)<=1024
    print('OK: client package hashes, exact DLL bounds, unchanged stock archive entries, all addon signatures, model key and graphics recovery guards.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('package',type=Path); args=parser.parse_args()
    try:verify(args.package)
    except Exception as e:print('FAIL:',e);sys.exit(1)
