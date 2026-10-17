"""Apply the published TEST12 patch locally; never accesses MIDI or network."""
import argparse,base64,hashlib,json
from pathlib import Path
STOCK='29fc1fb89a951a864e294764d2fe8bba4ad1ce890f9c308f09944749321571eb'
TARGET='9bc1c3a74da476c6694724314d275030a7debb4299c561d06cf56f4e55b540ef'
def sha(data):return hashlib.sha256(data).hexdigest()
def apply(data,patch):
    if patch.get('format')!='rd6-syx-replacements-v1' or patch.get('source_sha256')!=STOCK or patch.get('target_sha256')!=TARGET or len(data)!=patch.get('size') or sha(data)!=STOCK:
        raise ValueError('Requires the exact user-supplied stock RD-6 1.0.5 SysEx file.')
    out=bytearray(data);end=0
    for offset,encoded in patch['runs']:
        payload=base64.b64decode(encoded,validate=True)
        if type(offset) is not int or offset<end or not payload or offset+len(payload)>len(out):raise ValueError('Invalid/overlapping patch range')
        out[offset:offset+len(payload)]=payload;end=offset+len(payload)
    if sha(out)!=TARGET:raise ValueError('Patched TEST12 checksum mismatch')
    return bytes(out)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stock',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    data=apply(a.stock.read_bytes(),json.loads((Path(__file__).resolve().parents[1]/'outputs/TEST12.patch.json').read_text()))
    # Exclusive create protects original firmware and existing backups.
    with a.output.open('xb') as f:f.write(data)
    print('Prepared TEST12 locally:',sha(data));print('Original firmware file unchanged; keep it for possible restoration. No device readback was performed.')
if __name__=='__main__':main()
