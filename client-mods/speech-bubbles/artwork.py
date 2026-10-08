"""Archive helpers for native client resources."""
import sys, io, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'transmog-menu'))
from codec import read_pak, encode_pak, binary_xml, encode_binary_xml
def rewrite(path, changes):
    data=io.BytesIO()
    with read_pak(path) as original, zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as target:
        for info in original.infolist(): target.writestr(info,changes.get(info.filename,original.read(info.filename)))
        for name,payload in changes.items():
            if name not in original.namelist(): target.writestr(name,payload)
    return encode_pak(data.getvalue())
