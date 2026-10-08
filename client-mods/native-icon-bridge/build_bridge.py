"""Compile a self-contained x64 DLL, then create an index for this original client."""
import hashlib
import os
import json
import subprocess
from pathlib import Path
from prepare_index import prepare
from patch_client import AWESOMIUM_SHA256

def build(client, output, origin='http://127.0.0.1:8091', source_dir=None, index_client=None):
    awesomium = client / 'bin64/Awesomium.dll'
    if hashlib.sha256(awesomium.read_bytes()).hexdigest() != AWESOMIUM_SHA256:
        raise ValueError('Native icon bridge requires the verified 4.8 NA Awesomium.dll')
    source = Path(source_dir) if source_dir else Path(__file__).resolve().parent
    target = output / 'bin64'
    target.mkdir(parents=True, exist_ok=True)
    # Keep compiler intermediates outside the installer payload.
    work = output.parent / (output.name + '-native-build')
    work.mkdir(parents=True, exist_ok=True)
    if not origin.isascii() or '\n' in origin or '\r' in origin:
        raise ValueError('Invalid native icon origin')
    (work / 'release_origin.h').write_text('#define AION_ICON_ORIGIN ' + json.dumps(origin) + '\n', encoding='ascii')
    program_files = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
    vcvars = program_files / 'Microsoft Visual Studio/2022/BuildTools/VC/Auxiliary/Build/vcvars64.bat'
    if not vcvars.exists():
        raise ValueError('Install Visual Studio 2022 C++ Build Tools, or edit build_bridge.py for your MSVC installation')
    command = f'call "{vcvars}" >nul && cl /nologo /std:c++17 /EHsc /O2 /MT /LD /I"{work}" /Fo:"{work / "icon_bridge.obj"}" "{source / "icon_bridge.cpp"}" /link /OUT:"{target / "AionIconBridge.dll"}" /IMPLIB:"{work / "icon_bridge.lib"}" windowscodecs.lib ole32.lib bcrypt.lib user32.lib'
    script = work / 'compile.cmd'
    script.write_text('@echo off\n' + command + '\n', encoding='utf-8')
    # A raw command line preserves cmd.exe's nested quotes; list2cmdline escapes
    # them as C-runtime arguments, which breaks a quoted CALL path.
    subprocess.run(f'cmd.exe /d /s /c ""{script}""', check=True)
    result = prepare(index_client or client, target / 'AionIconBridge.index')
    result['awesomiumSha256'] = AWESOMIUM_SHA256
    result['origin'] = origin
    print('Original client icon bridge:', result)
    return result
