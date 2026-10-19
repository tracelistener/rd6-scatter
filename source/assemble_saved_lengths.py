"""Development assembler for source/saved_lengths.py (needs keystone); the generated
bytes are stored in that file, so building and checking need only capstone."""
import re
from pathlib import Path
import saved_lengths as L
import mute_roll as V
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS

at, addresses, bodies = L.START, {}, {}
for name in L.ORDER:
    source = L.listing(name, addresses.get('APPLY', 0))
    code = bytearray(Ks(KS_ARCH_ARM, KS_MODE_THUMB).asm('.arch armv7e-m\n' + source, at)[0])
    instrs, _ = L.parse(source)
    decoded = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS).disasm(bytes(code), at, len(instrs)))
    for (_, mnemonic, operands), ins in zip(instrs, decoded):
        if mnemonic in ('bl', 'b.w') and operands.startswith('0x'):
            code[ins.address - at:ins.address - at + 4] = L.branch(ins.address, int(operands, 16), mnemonic == 'bl')
    V.SOURCE['LEN_' + name] = source
    problems = V.check_branches('LEN_' + name, at, bytes(code))
    assert not problems, problems
    addresses[name], bodies[name] = at, bytes(code)
    print(name, hex(at), len(code))
    at = (at + len(code) + 3) & ~3
path = Path(__file__).with_name('saved_lengths.py')
text = path.read_text()
generated = '# GENERATED\nADDRESS = ' + repr({k: hex(v) for k, v in addresses.items()}).replace("'0x", '0x').replace("',", ',').replace("'}", '}') + '\nBODY = {\n'
generated += ''.join(f"    {n!r}: bytes.fromhex('{c.hex()}'),\n" for n, c in bodies.items())
generated += '}\n# END GENERATED'
path.write_text(re.sub(r'# GENERATED.*?# END GENERATED', lambda _: generated, text, flags=re.S), newline='\n')
