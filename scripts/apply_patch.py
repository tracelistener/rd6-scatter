"""Apply a published Scatter patch locally; never accesses MIDI or network."""
import argparse,base64,hashlib,json
from pathlib import Path
STOCK='29fc1fb89a951a864e294764d2fe8bba4ad1ce890f9c308f09944749321571eb'
TARGETS={'test12':'9bc1c3a74da476c6694724314d275030a7debb4299c561d06cf56f4e55b540ef','test14':'2cdce8d2ae225feb21a153d69669c3406410893e9d1882ac0c8fb5391468b97b'}
def sha(data):return hashlib.sha256(data).hexdigest()
def apply(data,patch):
    if patch.get('format')!='rd6-syx-replacements-v1' or patch.get('source_sha256')!=STOCK or patch.get('target_sha256') not in TARGETS.values() or len(data)!=patch.get('size') or sha(data)!=STOCK:
        raise ValueError('Requires the exact stock RD-6 1.0.5 SysEx file from firmware/.')
    out=bytearray(data);end=0
    for offset,encoded in patch['runs']:
        payload=base64.b64decode(encoded,validate=True)
        if type(offset) is not int or offset<end or not payload or offset+len(payload)>len(out):raise ValueError('Invalid/overlapping patch range')
        out[offset:offset+len(payload)]=payload;end=offset+len(payload)
    if sha(out)!=patch['target_sha256']:raise ValueError('Patched Scatter checksum mismatch')
    return bytes(out)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stock',type=Path);p.add_argument('output',type=Path);p.add_argument('--build',choices=TARGETS,default='test14');a=p.parse_args()
    data=apply(a.stock.read_bytes(),json.loads((Path(__file__).resolve().parents[1]/('outputs/'+a.build.upper()+'.patch.json')).read_text()))
    # Exclusive create protects original firmware and existing backups.
    with a.output.open('xb') as f:f.write(data)
    print('Prepared '+a.build.upper()+' locally:',sha(data));print('Original firmware file unchanged; keep it for possible restoration. No device readback was performed.')
if __name__=='__main__':main()
