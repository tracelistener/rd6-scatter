"""Build Scatter v1.2, outputs/scatter-v1.2.patch.json: Scatter v1 plus
- step lights that follow the step Scatter plays (source/step_lights.py), and
- Scatter staying on when Pattern Play switches to Pattern Write (source/mode_keep.py).

Decoding stays in memory; the only file written is the patch, as byte runs on
the official 1.0.5 SysEx file like the v1 patch. Update-file format, as checked
by the updater: data frames carry the image XOR a repeating 128-byte mask,
7-bit packed (each group's first byte holds the next seven bytes' top bits),
and the header frame stores the image size (bytes 10-13) and the 32-bit sum of
all image bytes (bytes 14-17), each as four 7-bit digits, low digit first. The
updater recovers the mask from the longest run of identical 128-byte blocks and
needs at least 100; v1's run of exactly 100 starts at 0x0800CE00, so new code
must stay below that address.
"""
from collections import Counter
from pathlib import Path
import base64, hashlib, json, sys
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'source')); sys.path.insert(0, str(HERE / 'scripts'))
from apply_patch import apply, STOCK
import step_lights as L
import mode_keep as M
BASE = 0x08002800
FREE_END = 0x0800CE00
OUT = HERE / 'outputs/scatter-v1.2.patch.json'
# (site, original bytes, new bytes, cave, routine)
CHANGES = [
    (L.SITE, L.SITE_STOCK, L.SITE_BL, L.CAVE, L.BODY),
    (M.PANEL_SITE, M.PANEL_SITE_STOCK, M.PANEL_SITE_NEW, M.PANEL_CAVE, M.PANEL_BODY),
    (M.DIRECTION_SITE, M.DIRECTION_SITE_STOCK, M.DIRECTION_SITE_NEW, M.DIRECTION_CAVE, M.DIRECTION_BODY),
]

def frames(data):
    out, at = [], 0
    while at < len(data):
        assert data[at] == 0xF0
        end = data.index(0xF7, at); out.append(bytes(data[at:end + 1])); at = end + 1
    return out

def unpack(packed):
    raw = bytearray()
    for i in range(0, len(packed), 8):
        group = packed[i:i + 8]
        raw.extend(value | (((group[0] >> (6 - j)) & 1) << 7) for j, value in enumerate(group[1:]))
    return bytes(raw)

def pack(raw):
    out = bytearray()
    for i in range(0, len(raw), 7):
        chunk = raw[i:i + 7]
        out.append(sum(((b >> 7) & 1) << (6 - j) for j, b in enumerate(chunk)))
        out.extend(b & 0x7F for b in chunk)
    return bytes(out)

def longest_run(image):
    n, best, start = len(image) // 128, 0, 0
    for i in range(1, n + 1):
        if i < n and image[i * 128:(i + 1) * 128] == image[start * 128:(start + 1) * 128]: continue
        best, start = max(best, i - start), i
    return best

def le7(value):
    assert 0 <= value < 1 << 28
    return bytes((value >> (7 * k)) & 0x7F for k in range(4))

def build(stock_syx, v1_patch):
    v1 = apply(stock_syx, v1_patch)
    fr = frames(v1)
    assert len(fr) == 383 and fr[5][8] == 0x0A
    payloads = [f[14:-1] for f in fr[6:]]
    lengths = [len(unpack(p)) for p in payloads]
    raw = b''.join(unpack(p) for p in payloads)
    blocks = [raw[i:i + 128] for i in range(0, len(raw) // 128 * 128, 128)]
    mask, count = Counter(blocks).most_common(1)[0]
    assert count >= 100
    image = bytearray(b ^ mask[i % 128] for i, b in enumerate(raw))
    header = fr[5]
    assert sum(image) & 0xFFFFFFFF == sum((header[14 + k] & 0x7F) << (7 * k) for k in range(4)), 'v1 header checksum'
    used = set()
    for site, original, new, cave, body in CHANGES:
        assert image[site - BASE:site - BASE + 4] == original, f'unexpected code at {site:#x}'
        span = set(range(cave, cave + len(body)))
        assert not span & used and cave + len(body) <= FREE_END, f'cave {cave:#x} overlaps or crosses {FREE_END:#x}'
        assert set(image[cave - BASE:cave - BASE + len(body)]) == {0}, f'cave {cave:#x} is not free'
        used |= span
        image[site - BASE:site - BASE + 4] = new
        image[cave - BASE:cave - BASE + len(body)] = body
    new_raw = bytes(b ^ mask[i % 128] for i, b in enumerate(image))
    out = list(fr[:5])
    out.append(header[:14] + le7(sum(image) & 0xFFFFFFFF) + header[18:])
    at = 0
    for f, n in zip(fr[6:], lengths):
        out.append(f[:14] + pack(new_raw[at:at + n]) + f[-1:]); at += n
    syx = b''.join(out)
    assert len(syx) == len(v1)
    assert longest_run(image) >= 100, 'the updater needs >= 100 identical blocks to recover the mask'
    return syx, bytes(image)

def patch_doc(stock_syx, target):
    runs, i = [], 0
    while i < len(target):
        if target[i] == stock_syx[i]: i += 1; continue
        j = i
        while j < len(target) and (target[j] != stock_syx[j] or target[j:j + 4] != stock_syx[j:j + 4]): j += 1
        runs.append([i, base64.b64encode(target[i:j]).decode()]); i = j
    return {'format': 'rd6-syx-replacements-v1', 'source_sha256': STOCK, 'target_sha256': hashlib.sha256(target).hexdigest(), 'size': len(target), 'runs': runs}

def main():
    stock = (HERE / 'firmware/RD-6_V1.0.5.syx').read_bytes()
    syx, image = build(stock, json.loads((HERE / 'source/scatter-v1.patch.json').read_text()))
    doc = patch_doc(stock, syx)
    text = json.dumps(doc, separators=(',', ':'))
    if OUT.exists() and OUT.read_text() != text: raise SystemExit(f'{OUT} exists with different contents; not overwriting.')
    OUT.write_text(text)
    print(json.dumps({'patch': str(OUT.relative_to(HERE)), 'syx_sha256': doc['target_sha256'], 'image_sha256': hashlib.sha256(image).hexdigest(), 'runs': len(doc['runs'])}, indent=2))

if __name__ == '__main__': main()
