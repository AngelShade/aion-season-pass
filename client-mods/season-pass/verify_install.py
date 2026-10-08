"""Exercise real installer and byte-exact restore against a disposable client copy."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from prepare import sha

HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    package=args.package.resolve();out=args.output.resolve()
    if out.exists():raise ValueError('Use a new disposable test directory')
    m=json.loads((package/'manifest.json').read_text());source=Path(m['clientRoot']).resolve();clone=out/'client';prepared=out/'prepared'
    if source==out or source in out.parents:raise ValueError('Test output must be outside the installed client')
    shutil.copytree(package,prepared)
    for rel in {e['path'] for e in m['files']+m['preservedFiles']}:
        if not (source/rel).is_file():
            assert any(e['path']==rel and e['original'] is None for e in m['files']),rel
            continue
        target=clone/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/rel,target)
    m['clientRoot']=str(clone);(prepared/'manifest.json').write_text(json.dumps(m,indent=2))
    command=[shutil.which('pwsh') or 'powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File']
    def run(name,arg,path,ok=True):
        r=subprocess.run(command+[str(HERE/name),arg,str(path)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        assert (r.returncode==0)==ok,(name,r.stdout,r.stderr)
        return r
    run('install.ps1','-PreparedPath',prepared)
    for e in m['files']:assert sha((clone/e['path']).read_bytes())==e['installed'],e['path']
    for e in m['preservedFiles']:assert sha((clone/e['path']).read_bytes())==e['sha256'],e['path']
    run('install.ps1','-PreparedPath',prepared,ok=False)
    backups=list((clone/'SeasonPass-backups').iterdir());assert len(backups)==1
    run('restore.ps1','-BackupPath',backups[0])
    for e in m['files']:
        assert (not (clone/e['path']).exists()) if e['original'] is None else sha((clone/e['path']).read_bytes())==e['original'],e['path']
    # A changed prepared DLL is rejected before any replacement occurs.
    dll=prepared/'bin64/Game.dll';data=bytearray(dll.read_bytes());data[-1]^=1;dll.write_bytes(data)
    run('install.ps1','-PreparedPath',prepared,ok=False)
    for e in m['files']:
        assert (not (clone/e['path']).exists()) if e['original'] is None else sha((clone/e['path']).read_bytes())==e['original'],e['path']
    print('OK: real PowerShell install, preserved files, repeated-install rejection, byte-exact restore and tamper rejection. Installed client untouched.')
if __name__=='__main__':main()
