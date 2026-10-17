"""Compile the three TEST12 LLVM payloads and verify pinned object bytes.
No firmware, MIDI, network or persistent object-file writes.
"""
from pathlib import Path
import hashlib,json
import llvmlite, llvmlite.binding as llvm
if llvmlite.__version__!='0.46.0' or llvm.llvm_version_info!=(20,1,8):raise RuntimeError('Use llvmlite0.46.0 / LLVM20.1.8')
llvm.initialize_all_targets();llvm.initialize_all_asmprinters()
root=Path(__file__).resolve().parent
for name,expected in json.loads((root/'objects.json').read_text()).items():
    module=llvm.parse_assembly((root/name).read_text());module.verify()
    machine=llvm.Target.from_triple('thumbv7em-none-eabi').create_target_machine(cpu='cortex-m4',opt=2)
    obj=machine.emit_object(module)
    assert hashlib.sha256(obj).hexdigest()==expected,name
    print('PASS',name)
