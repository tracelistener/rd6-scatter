"""Compare the actual saved Thumb fix to stock1.0.6; no device access."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from apply_patch import apply
from rd6_thumb_machine import Program,Memory,Thumb
from fix106_backport import SITE,CAVE
BASE=0x08002800

HERE=Path(__file__).resolve().parents[1]
def execute(image,start,end,group,pending,current,queued,patched=False):
    program=Program()
    if patched:
        program.add('site',SITE,image[SITE-BASE:SITE-BASE+4])
        program.add('fix',CAVE,image[CAVE-BASE:CAVE-BASE+22])
    else:program.add('stock106',start,image[start-BASE:end-BASE])
    memory=Memory();memory.add('flash',BASE,image);memory.add('ram',0x20000000,16384,writable=True)
    cur=0x20001000;queue=cur+20;selected=0x20001100
    memory.poke(cur+8,current,4);memory.poke(cur+12,current+100,4)
    memory.poke(queue,pending,4);memory.poke(queue+8,queued,4);memory.poke(queue+12,queued+100,4)
    memory.poke(selected,group,1)
    vm=Thumb(memory,program);vm.regs[0]=group if patched else 1
    vm.regs[1]=queue;vm.regs[3]=cur;vm.regs[4]=selected;vm.regs[5]=1
    status,count=vm.run(start,{end},100)
    assert status=='stop'
    return bytes(memory.region(0x20000000,16384).data)

def decode_syx(data):
    frames=[];at=0
    while at<len(data):
        assert data[at]==240
        end=data.index(247,at);frames.append(data[at:end+1]);at=end+1
    raw=bytearray()
    for frame in frames[6:]:
        packed=frame[14:-1]
        for i in range(0,len(packed),8):
            group=packed[i:i+8]
            raw.extend(value|(((group[0]>>(6-j))&1)<<7) for j,value in enumerate(group[1:]))
    blocks=[bytes(raw[i:i+128]) for i in range(0,len(raw)//128*128,128)]
    from collections import Counter
    mask,count=Counter(blocks).most_common(1)[0];assert count>=100
    return bytes(value^mask[i%128] for i,value in enumerate(raw))

def main():
    data=(HERE/'firmware/RD-6_V1.0.5.syx').read_bytes()
    new=decode_syx(apply(data,json.loads((HERE/'outputs/TEST14.patch.json').read_text())))
    parent=decode_syx(apply(data,json.loads((HERE/'outputs/TEST12.patch.json').read_text())))
    stock=decode_syx((HERE/'firmware/RD-6_V1.0.6.syx').read_bytes())
    allowed=set(range(SITE-BASE,SITE-BASE+4))|set(range(CAVE-BASE,CAVE-BASE+22))
    assert {i for i,(a,b) in enumerate(zip(parent,new)) if a!=b}<=allowed
    cases=0
    for group in (0,1):
        for pending in (0,1,2):
            for current in range(16):
                for queued in range(16):
                    actual=execute(new,SITE,0x08005c98,group,pending,current,queued,True)
                    expected=execute(stock,0x08005c70,0x08005c92,group,pending,current,queued)
                    assert actual==expected,(group,pending,current,queued)
                    want=queued if pending else current
                    assert int.from_bytes(actual[0x101c:0x1020],'little')==want
                    cases+=1
    report={'status':'passed_saved_Thumb_stock106_fix_equivalence','candidate_sha256':hashlib.sha256(new).hexdigest(),'state_comparisons':cases,'changes_limited_to_4_byte_hook_and_22_byte_fix':True,'TEST12_effect_panel_timer_and_startup_bytes_unchanged':True,'scope':'Actual saved Thumb code and stock1.0.6 branch compared over both groups, queued/no-queue states, all16 current and requested pattern numbers. No physical test or full MCU emulation.'}
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
