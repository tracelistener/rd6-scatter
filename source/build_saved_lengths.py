"""Build Scatter v1.4.1, outputs/scatter-v1.4.1.patch.json: the MIDI
extra-hit build plus each voice's length saved with its pattern, shown in Pattern Write and
easier to set (source/saved_lengths.py).

Decoding stays in memory; the only file written is the patch, as byte runs on the official
1.0.5 SysEx file. The new code follows the MIDI routines from 0x0800D300.
"""
from pathlib import Path
import hashlib, json, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_scatter_v1_3 import HERE, BASE, MIN_RUN, decode, encode
from build_scatter_v1_2 import patch_doc, longest_run
from apply_patch import apply
import saved_lengths as L
import mute_roll as V

OUT = HERE / 'outputs/scatter-v1.4.1.patch.json'
MIDI = HERE / 'source/scatter-v1.3-midi-test.patch.json'


def build(stock):
    syx = apply(stock, json.loads(MIDI.read_text()))
    fr, lengths, mask, image = decode(syx)
    for name, site, old, new in L.sites():
        assert image[site - BASE:site - BASE + 4] == old, f'unexpected bytes at {site:#x} ({name})'
        image[site - BASE:site - BASE + 4] = new
    end = L.START
    for name in L.ORDER:
        at, code = L.ADDRESS[name], L.BODY[name]
        assert at >= end and at % 4 == 0 and at + len(code) <= 0x0800D600, f"{name} is outside its blocks"
        assert set(image[at - BASE:at - BASE + len(code)]) == {0}, f'{name} space is not free'
        V.SOURCE['LEN_' + name] = L.listing(name, L.ADDRESS['APPLY'])
        assert not V.check_branches('LEN_' + name, at, code), f'{name} branches differ from the listing'
        image[at - BASE:at - BASE + len(code)] = code
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
    OUT.write_text(text, newline='\n')
    print(json.dumps({'patch': OUT.relative_to(HERE).as_posix(), 'syx_sha256': doc['target_sha256'],
                      'image_sha256': hashlib.sha256(image).hexdigest(), 'runs': len(doc['runs']),
                      'mask_run_blocks': longest_run(image)}, indent=2))
