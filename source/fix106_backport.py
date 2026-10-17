"""TEST14's queued-pattern fix. Original implementation; no stock image here.
Requires the established encode_bl linker helper to assemble its two branches.
SITE jumps to CAVE; the cave checks pending, conditionally copies current pattern,
then updates group and queued flag. The caller-saved r2 register is dead here.
"""
SITE=0x08005c74
CAVE=0x0800bdc0
RETURN=0x08005c98
THUMB_BODY=bytes.fromhex('0a68002a03d19a688a60da68ca6008740d60')
