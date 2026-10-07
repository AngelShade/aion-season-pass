"""Incremental native pass integration. Stages files only; preserves all other installed hooks."""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'transmog-menu'))
sys.path.insert(0, str(HERE.parent/'speech-bubbles'))
import patch_game_dll as p
from artwork import read_pak, rewrite
import shortcut

PASS_URL = 'http://127.0.0.1:8091/market/pass'
OLD_ROUTES = ['http://127.0.0.1:8091/shop', 'http://127.0.0.1:8091/market', 'http://127.0.0.1:8091/market/wardrobe', 'http://127.0.0.1:8091/journey']
AUTH = p.build_market_auth_code(OLD_ROUTES[1:], compact=False)
BROWSER = p.build_browser_hook_code(OLD_ROUTES)
NEW_AUTH = p.build_market_auth_code(OLD_ROUTES[1:]+[PASS_URL], compact=True)
NEW_BROWSER = p.build_browser_hook_code(OLD_ROUTES+[PASS_URL])
PRESERVED = ['Pub.key','bin64/crysystem.dll','bin64/AionIconBridge.dll','bin64/AionGraphicsMenu.dll','bin64/XRenderD3D9.dll','bin32/bin32.pak','Data/func_pet/func_pet.pak','Data/ui/game/game.pak','Data/Items/Items.pak']

def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))

def market_hooks(root):
    backups=root/'MarketShortcut-backups'
    if not backups.is_dir(): raise ValueError('Install the supported Central Market HUD patch before Season Pass')
    for manifest in sorted(backups.glob('*/manifest.json'),reverse=True):
        try:
            receipt=read(manifest)
            if receipt.get('feature')=='central-market-hud' and receipt.get('hooks',{}).get('bin64/Game.dll'):
                return receipt['hooks']
        except (OSError,ValueError,KeyError,TypeError): pass
    raise ValueError('Could not find a valid Central Market HUD recovery receipt')

def patch(data,new_auth=NEW_AUTH,new_browser=NEW_BROWSER):
    if data[p.MARKET_AUTH_HOOK_RVA:p.MARKET_AUTH_HOOK_RVA+len(AUTH)] != AUTH:
        raise ValueError('Installed native authentication hook differs from the verified four-window build')
    if data[p.BROWSER_HOOK_RVA:p.BROWSER_HOOK_RVA+len(BROWSER)] != BROWSER:
        raise ValueError('Installed browser route hook differs')
    if any(data[p.MARKET_AUTH_HOOK_RVA+len(AUTH):p.MARKET_RECT_HOOK_RVA]) or any(data[p.BROWSER_HOOK_RVA+len(BROWSER):p.PREVIEW_DOCK_HOOK_RVA]):
        raise ValueError('Browser code cave contains an unknown extension')
    if len(new_auth)>p.MARKET_RECT_HOOK_RVA-p.MARKET_AUTH_HOOK_RVA or len(new_browser)>p.PREVIEW_DOCK_HOOK_RVA-p.BROWSER_HOOK_RVA:
        raise ValueError('Pass hook exceeds existing caves')
    # Entry jumps, viewport layout, inventory, speech, cursor and graphics hooks stay intact.
    out=bytearray(data)
    out[p.MARKET_AUTH_HOOK_RVA:p.MARKET_RECT_HOOK_RVA]=new_auth.ljust(p.MARKET_RECT_HOOK_RVA-p.MARKET_AUTH_HOOK_RVA,b'\0')
    out[p.BROWSER_HOOK_RVA:p.PREVIEW_DOCK_HOOK_RVA]=new_browser.ljust(p.PREVIEW_DOCK_HOOK_RVA-p.BROWSER_HOOK_RVA,b'\0')
    return bytes(out)

def menu(data,pass_url=PASS_URL):
    if b'PRIVATESEASONPASS' in data: raise ValueError('Season pass is already registered')
    text=data.decode('utf-8').replace('\r\n','\n')
    anchor='function PrivateMenus_Register()\n'
    if text.count(anchor)!=1 or text.count('function PrivateWarehouse_Open()')!=1: raise ValueError('Unexpected installed menu')
    if 'PRIVATE_CENTRAL_MARKET_URL = "http://127.0.0.1:8091/market"' not in text: raise ValueError('Unexpected native market URL')
    source=(HERE.parent/'transmog-menu/PrivateMenus.lua').read_text(encoding='utf-8')
    function=re.search(r'function PrivateSeasonPass_Open\(\)\n.*?\nend\n',source,re.S).group()
    text='PRIVATE_SEASON_PASS_URL = '+json.dumps(PASS_URL)+';\n'+function+'\n'+text
    insertion='    SlashCmdList["PRIVATESEASONPASS"] = PrivateSeasonPass_Open;\n    SLASH_PRIVATESEASONPASS1 = "/seasonpass";\n    RegisterMenu("Aetherfall Season Pass", SLASH_PRIVATESEASONPASS1, "season_ticket_up");\n'
    text=text.replace(anchor,anchor+insertion)
    text=text.replace('function PrivateWarehouse_Open()\n', 'function PrivateWarehouse_Open()\n    PrivateWarehouse:SetText("Central Market");\n')
    return text.replace('\n','\r\n').encode('utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--server-url',default='http://127.0.0.1:8091',help='HTTPS origin used by remote players, or loopback for same-PC use')
    args=parser.parse_args(); root=args.client.resolve(); out=args.output.resolve()
    server=urlsplit(args.server_url.rstrip('/'))
    if (server.scheme not in ('http','https') or not server.netloc or server.username or server.password
        or server.path or server.query or server.fragment or not server.hostname):
        raise ValueError('--server-url must be an origin such as https://play.example.com')
    if server.scheme!='https' and server.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Remote players require HTTPS; plain HTTP is allowed only for loopback testing')
    origin=server.scheme+'://'+server.netloc
    pass_url=origin+'/market/pass'
    new_auth=p.build_market_auth_code(OLD_ROUTES[1:]+[pass_url],compact=True)
    new_browser=p.build_browser_hook_code(OLD_ROUTES+[pass_url])
    if out.exists() or out==root or root in out.parents: raise ValueError('Use a new output directory outside the client')
    staged={}
    def stage(rel,data):
        rel=Path(rel).as_posix(); target=out/rel
        if rel in staged and staged[rel]!=data: raise ValueError('Conflicting recovery payload: '+rel)
        staged[rel]=data; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    stage('bin64/Game.dll',patch((root/'bin64/Game.dll').read_bytes(),new_auth,new_browser))
    pak='Plugin/RelicCalc/RelicCalc.pak'; archive=read_pak(root/pak)
    # Confirm Dialog inherits the stock SetText method used by this client.
    stage(pak,rewrite(root/pak,{'PrivateMenus.lua':menu(archive.read('PrivateMenus.lua'),pass_url)}))
    definitions,texture=shortcut.artwork(out)
    for rel in shortcut.RESOURCES:stage(rel,shortcut.transform(root/rel,rel,definitions,texture))
    stage('bin64/AionMarketShortcut.dll',shortcut.compile_extension(out))
    subprocess.run(['java',str(HERE.parent/'transmog-menu/SignClientPackages.java'),str(root),str(out)],check=True)
    (out/'Pub.key').unlink()
    for rel in ['Addon.key','bin32/bin32.pak.sig','Data/func_pet/func_pet.pak.sig',pak+'.sig']:stage(rel,(out/rel).read_bytes())
    # Compose the current graphics/cursor recovery guards and their exact baselines.
    graphics=read(root/'DXVK/graphics-menu/installed.json')
    manifest=read(root/'DXVK/graphics-menu/package/manifest.json')
    if graphics['files']!=manifest['files']: raise ValueError('Graphics recovery metadata differs')
    entry=next(e for e in graphics['files'] if e['path']=='bin64/Game.dll')
    if sha((root/entry['path']).read_bytes())!=entry['installed']: raise ValueError('Live Game.dll no longer matches graphics guards')
    baseline=Path(graphics['backupRoot'])/entry['path']
    if not baseline.resolve().is_relative_to(root/'DXVK-backups') or sha(baseline.read_bytes())!=entry['original']: raise ValueError('Graphics baseline differs')
    stage(baseline.relative_to(root),patch(baseline.read_bytes(),new_auth,new_browser))
    entry['original']=sha(staged[baseline.relative_to(root).as_posix()]); entry['installed']=sha(staged['bin64/Game.dll'])
    locale=next(e for e in graphics['files'] if e['path']=='L10N/enu/Data/data.pak')
    locale_baseline=Path(graphics['backupRoot'])/locale['path']
    if not locale_baseline.resolve().is_relative_to(root/'DXVK-backups') or sha(locale_baseline.read_bytes())!=locale['original'] or sha((root/locale['path']).read_bytes())!=locale['installed']:raise ValueError('Graphics locale recovery guards differ')
    stage(locale_baseline.relative_to(root),shortcut.transform(locale_baseline,locale['path'],definitions,texture))
    locale.update(original=sha(staged[locale_baseline.relative_to(root).as_posix()]),installed=sha(staged[locale['path']]))
    stage('DXVK/graphics-menu/package/'+locale['path'],staged[locale['path']])
    manifest['files']=graphics['files']
    stage('DXVK/graphics-menu/installed.json',json.dumps(graphics,indent=2).encode())
    stage('DXVK/graphics-menu/package/manifest.json',json.dumps(manifest,indent=2).encode())
    stage('DXVK/graphics-menu/package/bin64/Game.dll',staged['bin64/Game.dll'])
    cursor=read(root/'DXVK/installed.json'); entry=next(e for e in cursor['nativeCursorPatch']['files'] if e['path']=='bin64/Game.dll')
    baseline=Path(entry['backupPath'])
    if not baseline.resolve().is_relative_to(root/'DXVK-backups') or sha(baseline.read_bytes())!=entry['original']: raise ValueError('Cursor recovery baseline differs')
    stage(baseline.relative_to(root),patch(baseline.read_bytes(),new_auth,new_browser))
    entry['original']=sha(staged[baseline.relative_to(root).as_posix()]); entry['installed']=sha(staged['bin64/Game.dll'])
    stage('DXVK/installed.json',json.dumps(cursor,indent=2).encode())
    # Earlier Market/Speech rollback receipts remain intact. Their source-hash
    # guards correctly require removing this later pass patch first.
    files=[dict(path=rel,original=sha((root/rel).read_bytes()) if (root/rel).is_file() else None,installed=sha(data)) for rel,data in staged.items()]
    receipt=dict(feature='daeva-season-pass',clientRoot=str(root),serverUrl=origin,sourceKey=sha((root/'Pub.key').read_bytes()),files=files,
        preservedFiles=[dict(path=rel,sha256=sha((root/rel).read_bytes())) for rel in PRESERVED],
        allowedDllRanges=[[p.MARKET_AUTH_HOOK_RVA,p.MARKET_RECT_HOOK_RVA],[p.BROWSER_HOOK_RVA,p.PREVIEW_DOCK_HOOK_RVA]],
        shortcut=dict(widget='season_pass_button',command='/seasonpass',skin='season_ticket_button',placement='above-central-market',height=32,gap=2),
        hooks=market_hooks(root))
    (out/'manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('OK: prepared',len(files),'incremental client files. The installed client has not been modified.')
if __name__=='__main__': main()
