"""Build the MIDI extra-hit test patch on Scatter v1.3,
outputs/scatter-v1.3-midi-test.patch.json (source/midi_extra.py).

Decoding stays in memory; the only file written is the patch, as byte runs on the
official 1.0.5 SysEx file. The new code takes the block after v1.3's code, from
0x0800D200, so the updater's mask run drops from 92 to 90 blocks; it needs 64.
"""
from pathlib import Path
import hashlib, json, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_scatter_v1_3 import HERE, BASE, MIN_RUN, decode, encode
from build_scatter_v1_2 import patch_doc, longest_run
from apply_patch import apply
import midi_extra as M
import mute_roll as V

OUT = HERE / 'outputs/scatter-v1.3-midi-test.patch.json'
V13 = HERE / 'outputs/scatter-v1.3.patch.json'


def build(stock):
    syx = apply(stock, json.loads(V13.read_text()))
    fr, lengths, mask, image = decode(syx)
    for site, old, new in M.sites():
        assert image[site-BASE:site-BASE+4] == old, f'unexpected bytes at {site:#x}'
        image[site-BASE:site-BASE+4] = new
    assert image[M.MID_RESUME-BASE:M.MID_RESUME-BASE+4] == bytes.fromhex('28680028'), "v1.3's t_done"
    end = M.START
    for name in M.ORDER:
        at, code = M.ADDRESS[name], M.BODY[name]
        assert at >= end and at % 4 == 0 and at + len(code) <= 0x0800D300, f'{name} is outside its block'
        assert set(image[at-BASE:at-BASE+len(code)]) == {0}, f'{name} space is not free'
        V.SOURCE['MIDI_' + name] = M.listing(name, M.ADDRESS['SAFE'])
        assert not V.check_branches('MIDI_' + name, at, code), f'{name} branches differ from the listing'
        image[at-BASE:at-BASE+len(code)] = code
        end = at + len(code)
    assert longest_run(image) >= MIN_RUN, f'the updater needs >= {MIN_RUN} identical blocks to recover the mask'
    syx = encode(fr, lengths, mask, image)
    assert decode(syx)[2] == mask
    return syx, bytes(image)


if __name__ == '__main__':
    stock = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    syx, image = build(stock)
    doc = patch_doc(stock, syx)
    text = json.dumps(doc, separators=(',', ':'))
    if OUT.exists() and OUT.read_text() != text: raise SystemExit(f'{OUT} exists with different contents; not overwriting.')
    OUT.write_text(text)
    print(json.dumps({'patch': str(OUT.relative_to(HERE)), 'syx_sha256': doc['target_sha256'],
                      'image_sha256': hashlib.sha256(image).hexdigest(), 'runs': len(doc['runs']),
                      'mask_run_blocks': longest_run(image)}, indent=2))
