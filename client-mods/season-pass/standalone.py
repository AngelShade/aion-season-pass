"""Build the complete Season Pass browser, signing, native icons and HUD for the supported original client."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'transmog-menu'))
sys.path.insert(0, str(HERE.parent / 'speech-bubbles'))
import patch_game_dll as native
from patch_plugin_key import patch_plugin_key
from artwork import read_pak, rewrite, binary_xml, encode_binary_xml
import shortcut

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def origin_url(value):
    value = value.rstrip('/')
    origin = urlsplit(value)
    if (origin.scheme not in ('http', 'https') or not origin.hostname or not origin.netloc
            or origin.username or origin.password or origin.path or origin.query or origin.fragment):
        raise ValueError('Use an origin such as https://play.example.com')
    if origin.scheme != 'https' and origin.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Remote players require HTTPS')
    host = origin.hostname.lower()
    if ':' in host: host = '[' + host + ']'
    port = origin.port
    if port is not None and not 1 <= port <= 65535: raise ValueError('Invalid origin port')
    if port == (443 if origin.scheme == 'https' else 80): port = None
    value = origin.scheme + '://' + host + (':' + str(port) if port is not None else '')
    route = value + '/market/pass'
    if not route.isascii() or len(route) > 190:
        raise ValueError('Use an ASCII HTTPS origin with a route of at most 190 characters')
    return value, route

def library(data, definitions):
    tree = binary_xml(data)
    category = tree.find(".//Category[@name='version5']")
    if category is None:
        category = tree.find(".//Category[@name='free_version']")
    if tree.tag != 'SkinLibrary' or category is None:
        raise ValueError('Unsupported original skin library')
    for definition in definitions:
        if tree.find(".//*[@name='" + definition.get('name') + "']") is not None:
            raise ValueError('Season Pass artwork already installed')
        category.append(definition)
    return encode_binary_xml(tree)

def hud(data, style):
    tree = binary_xml(data)
    if tree.get('name') != 'start_dialog' or tree.find(".//Widget[@name='season_pass_button']") is not None:
        raise ValueError('Unsupported or already modified HUD')
    ET.SubElement(tree, 'Widget', name='season_pass_button', type='button',
                  frame='64,53,34,32' if style == 1 else '77,35,34,32', flag='visible',
                  preset='season_ticket_button', tooltip=shortcut.TOOLTIP)
    return encode_binary_xml(tree)

def compile_shortcut(output, source=HERE / 'season_shortcut.cpp', suffix='shortcut'):
    work = output.parent / (output.name + '-' + suffix + '-build')
    work.mkdir()
    vcvars = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'
    if not vcvars.is_file():
        raise ValueError('Visual Studio 2022 C++ Build Tools with the Windows SDK are required')
    target = output / 'bin64/AionMarketShortcut.dll'
    target.parent.mkdir(exist_ok=True)
    script = work / 'compile.cmd'
    script.write_text('@echo off\ncall "' + str(vcvars) + '" >nul\nif errorlevel 1 exit /b 1\n'
        + 'cl /nologo /std:c++17 /EHsc /O2 /MT /LD /Fo:"' + str(work / 'shortcut.obj') + '" "'
        + str(source) + '" /link /OUT:"' + str(target)
        + '" /IMPLIB:"' + str(work / 'shortcut.lib') + '"\n', encoding='utf-8')
    subprocess.run('cmd.exe /d /s /c ""' + str(script) + '""', check=True)

def prepare(root, output, server_url):
    root, output = root.resolve(), output.resolve()
    origin, route = origin_url(server_url)
    if output.exists() or output == root or root in output.parents:
        raise ValueError('Use a new output directory outside the client')
    if sha(root / 'bin64/Game.dll') != native.ORIGINAL_SHA256:
        raise ValueError('Standalone preparation requires the supported original Game.dll')
    if (root / 'DXVK/installed.json').exists() or (root / 'DXVK/graphics-menu/installed.json').exists():
        raise ValueError('Use an original client for standalone preparation; preserve installed renderer recovery state')
    with read_pak(root / 'Plugin/RelicCalc/RelicCalc.pak') as archive:
        if 'PrivateMenus.lua' in archive.namelist():
            raise ValueError('Use an original client without a custom browser integration')
        lua = archive.read('RelicCalc.lua')
        toc = archive.read('RelicCalc.toc').decode('utf-8-sig').replace('\r', '').splitlines()
    anchor = b'\tRegisterMenu(GetAionStr("STR_RELICCALC_TITLE"), lastCommand, "v5_start_menu_relic_up");'
    if lua.count(anchor) != 1:
        raise ValueError('Original RelicCalc menu registration differs')
    output.mkdir(parents=True)
    def stage(relative, data):
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    xml = (HERE.parent / 'transmog-menu/Warehouse.xml').read_text(encoding='utf-8-sig')
    xml_bytes = xml.replace('UTF-8', 'UTF-16').replace('\n', '\r\n').encode('utf-16')
    ET.fromstring(xml_bytes)
    menu = 'PRIVATE_SEASON_PASS_URL = ' + json.dumps(route) + ';\n' + (HERE / 'StandaloneMenus.lua').read_text(encoding='utf-8')
    changes = {'RelicCalc.lua': lua.replace(anchor, b'\tPrivateMenus_Register();\r\n' + anchor),
               'Warehouse.xml': xml_bytes, 'PrivateMenus.lua': menu.replace('\n', '\r\n').encode('utf-8'),
               'RelicCalc.toc': ('\r\n'.join(toc + ['Warehouse.xml', 'PrivateMenus.lua']) + '\r\n').encode('utf-8')}
    stage('Plugin/RelicCalc/RelicCalc.pak', rewrite(root / 'Plugin/RelicCalc/RelicCalc.pak', changes))
    artwork_dir = output.parent / (output.name + '-artwork')
    artwork_dir.mkdir()
    definitions, texture = shortcut.artwork(artwork_dir)
    resources = {'Data/ui/ui.pak': {'UI_Preload.xml': library(read_pak(root / 'Data/ui/ui.pak').read('UI_Preload.xml'), definitions)},
                 'Textures/ui/ui.pak': {'season_ticket.dds': texture}}
    locale = 'L10N/enu/Data/data.pak'
    with read_pak(root / locale) as archive:
        resources[locale] = {'ui/ui_preload.xml': library(archive.read('ui/ui_preload.xml'), definitions),
                             'strings/client_strings_ui.xml': shortcut.strings(archive.read('strings/client_strings_ui.xml'))}
        for style in (1, 2):
            name = f'ui/game_hud_s{style}/start_dialog.xml'
            resources[locale][name] = hud(archive.read(name), style)
    for style in (1, 2):
        name = f'Data/ui/game_hud_s{style}/game_hud_s{style}.pak'
        resources[name] = {'start_dialog.xml': hud(read_pak(root / name).read('start_dialog.xml'), style)}
    for relative, replacements in resources.items():
        stage(relative, rewrite(root / relative, replacements))
        with read_pak(root / relative) as before, read_pak(output / relative) as after:
            if after.testzip() is not None or set(after.namelist()) != set(before.namelist()) | set(replacements):
                raise ValueError('Prepared native archive differs: ' + relative)
            for name in before.namelist():
                if name not in replacements and before.read(name) != after.read(name):
                    raise ValueError('Unrelated archive entry changed: ' + relative + '/' + name)
    dll = native.build_dll(root / 'bin64/Game.dll', [], [route])
    sys.path.insert(0, str(HERE.parent / 'native-icon-bridge'))
    from build_bridge import build as build_bridge
    from patch_client import patch_dll as icon_hook
    bridge = build_bridge(root, output, origin)
    dll = icon_hook(dll)
    sys.path.insert(0, str(HERE.parent / 'market-shortcut'))
    from patch_binary import patch as hud_hook
    dll, hooks = hud_hook(dll)
    stage('bin64/Game.dll', dll)
    stage('bin64/crysystem.dll', patch_plugin_key((root / 'bin64/crysystem.dll').read_bytes()))
    compile_shortcut(output)
    subprocess.run(['java', str(HERE.parent / 'transmog-menu/SignClientPackages.java'), str(root), str(output)], check=True)
    (output / 'Pub.key').unlink()
    files = [dict(path=f.relative_to(output).as_posix(), original=sha(root / f.relative_to(output)) if (root / f.relative_to(output)).is_file() else None,
                  installed=sha(f)) for f in sorted(output.rglob('*')) if f.is_file()]
    preserved = ['Pub.key', 'bin32/bin32.pak', 'Data/func_pet/func_pet.pak', 'Data/Items/Items.pak', 'bin64/Awesomium.dll']
    manifest = dict(feature='daeva-season-pass', mode='standalone', clientRoot=str(root), serverUrl=origin, sourceKey=sha(root / 'Pub.key'),
                    files=files, preservedFiles=[dict(path=p, sha256=sha(root / p)) for p in preserved],
                    hooks={'bin64/Game.dll': hooks}, nativeIcons=bridge,
                    shortcut=dict(widget='season_pass_button', command='/seasonpass', skin='season_ticket_button', placement='beside-stock-shop'))
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('OK: prepared', len(files), 'standalone Season Pass files; original client unchanged.')
