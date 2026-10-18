"""Build Scatter v1.3 from the official RD-6 1.0.5 SysEx file; never accesses MIDI or network."""
import argparse,base64,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STOCK='29fc1fb89a951a864e294764d2fe8bba4ad1ce890f9c308f09944749321571eb'
# Scatter v1.3 is v1.2 plus mute and roll mode and a loop length per voice (source/build_scatter_v1_3.py).
# v1.2 is v1 plus step lights that follow the played step and Scatter staying on in Pattern Write
# (source/build_scatter_v1_2.py). v1.2, v1 (developed as TEST14_FIX106) and TEST12 are kept in source/
# only so each build can be rebuilt from its parent and the checks can confirm what each one changes.
PATCHES={'scatter-v1':('source/scatter-v1.patch.json','2cdce8d2ae225feb21a153d69669c3406410893e9d1882ac0c8fb5391468b97b'),
         'scatter-v1.2':('source/scatter-v1.2.patch.json','8bbc359ebdf78357f7233556bf2843d53b34e8a1a52a4f1c0b8b83a9db9d41dc'),
         'test12':('source/TEST12.patch.json','9bc1c3a74da476c6694724314d275030a7debb4299c561d06cf56f4e55b540ef'),
         'scatter-v1.3':('outputs/scatter-v1.3.patch.json','ff0bb9d18ae7d926f780a65dddda53cb925cb544d3c46a2d5ae1472ff7848fc5')}
def sha(data):return hashlib.sha256(data).hexdigest()
def apply(data,patch):
    if patch.get('format')!='rd6-syx-replacements-v1' or patch.get('source_sha256')!=STOCK or patch.get('target_sha256') not in {t for _,t in PATCHES.values()} or len(data)!=patch.get('size') or sha(data)!=STOCK:
        raise ValueError('Requires the exact stock RD-6 1.0.5 SysEx file from firmware/.')
    out=bytearray(data);end=0
    for offset,encoded in patch['runs']:
        payload=base64.b64decode(encoded,validate=True)
        if type(offset) is not int or offset<end or not payload or offset+len(payload)>len(out):raise ValueError('Invalid/overlapping patch range')
        out[offset:offset+len(payload)]=payload;end=offset+len(payload)
    if sha(out)!=patch['target_sha256']:raise ValueError('Patched Scatter checksum mismatch')
    return bytes(out)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stock',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    data=apply(a.stock.read_bytes(),json.loads((ROOT/PATCHES['scatter-v1.3'][0]).read_text()))
    # Exclusive create protects original firmware and existing backups.
    with a.output.open('xb') as f:f.write(data)
    print('Prepared Scatter v1.3 locally:',sha(data));print('Original firmware file unchanged; keep it for possible restoration. No device readback was performed.')
if __name__=='__main__':main()
