"""Build Scatter v1.3, source/scatter-v1.3.patch.json: Scatter v1.2
plus mute and roll mode and a loop length per voice (source/mute_roll.py).

Decoding stays in memory; the only file written is the patch, as byte runs on the
official 1.0.5 SysEx file. The update-file helpers are the ones
source/build_scatter_v1_2.py uses. The new code takes 8 of the 100 blank blocks
from 0x0800CE00 that the updater recovers the mask from; the updater needs 64.
"""
from collections import Counter
from pathlib import Path
import hashlib, json, sys
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'source')); sys.path.insert(0, str(HERE / 'scripts'))
from apply_patch import apply
from build_scatter_v1_2 import frames, unpack, pack, longest_run, le7, patch_doc
import mute_roll as M
BASE = 0x08002800
MIN_RUN = 64
OUT = HERE / 'source/scatter-v1.3.patch.json'


def decode(syx, minimum=MIN_RUN):
    """Frames, unpacked length per data frame, mask and image of an update file."""
    fr = frames(syx)
    assert len(fr) == 383 and fr[5][8] == 0x0A
    payloads = [f[14:-1] for f in fr[6:]]
    lengths = [len(unpack(p)) for p in payloads]
    raw = b''.join(unpack(p) for p in payloads)
    blocks = [raw[i:i + 128] for i in range(0, len(raw) // 128 * 128, 128)]
    mask, count = Counter(blocks).most_common(1)[0]
    assert count >= minimum
    image = bytearray(b ^ mask[i % 128] for i, b in enumerate(raw))
    header = fr[5]
    assert sum(image) & 0xFFFFFFFF == sum((header[14 + k] & 0x7F) << (7 * k) for k in range(4)), 'header checksum'
    return fr, lengths, mask, image


def encode(fr, lengths, mask, image):
    raw = bytes(b ^ mask[i % 128] for i, b in enumerate(image))
    out = list(fr[:5])
    out.append(fr[5][:14] + le7(sum(image) & 0xFFFFFFFF) + fr[5][18:])
    at = 0
    for f, n in zip(fr[6:], lengths):
        out.append(f[:14] + pack(raw[at:at + n]) + f[-1:]); at += n
    return b''.join(out)


def build(stock_syx, v12_patch):
    v12 = apply(stock_syx, v12_patch)
    fr, lengths, mask, image = decode(v12, 100)
    for name, site, original, new in M.sites():
        assert image[site - BASE:site - BASE + 4] == original, f'unexpected bytes at {site:#x} ({name})'
        image[site - BASE:site - BASE + 4] = new
    end = M.START
    for name in M.ORDER:
        at, body = M.ADDRESS[name], M.BODY[name]
        assert at >= end and at % 4 == 0, f'{name} overlaps the previous routine'
        assert set(image[at - BASE:at - BASE + len(body)]) == {0}, f'{name} space is not free'
        assert not M.check_branches(name, at, body), f'{name} branches differ from the listing'
        image[at - BASE:at - BASE + len(body)] = body
        end = at + len(body)
    syx = encode(fr, lengths, mask, image)
    assert len(syx) == len(v12)
    assert longest_run(image) >= MIN_RUN, f'the updater needs >= {MIN_RUN} identical blocks to recover the mask'
    assert decode(syx)[2] == mask
    return syx, bytes(image)


def main():
    stock = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    syx, image = build(stock, json.loads((HERE / 'source/scatter-v1.2.patch.json').read_text()))
    doc = patch_doc(stock, syx)
    text = json.dumps(doc, separators=(',', ':'))
    if OUT.exists() and OUT.read_text() != text: raise SystemExit(f'{OUT} exists with different contents; not overwriting.')
    OUT.write_text(text)
    print(json.dumps({'patch': str(OUT.relative_to(HERE)), 'syx_sha256': doc['target_sha256'],
                      'image_sha256': hashlib.sha256(image).hexdigest(), 'runs': len(doc['runs']),
                      'mask_run_blocks': longest_run(image)}, indent=2))


if __name__ == '__main__': main()
