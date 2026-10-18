"""Direct-call firmware audit; images stay in memory. Indirect edges are reported."""
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone import arm_const as A
BASE = 0x08002800

def word(image, address):
    return int.from_bytes(image[address-BASE:address-BASE+4], 'little')

cs = Cs(CS_ARCH_ARM, CS_MODE_THUMB); cs.detail = True

def one(img, addr):
    for ins in cs.disasm(img[addr - BASE:addr - BASE + 4], addr, 1):
        return ins
    return None

def explore(img, entry, limit=4000):
    """Return (instructions set, calls set, tailcalls set, indirect list) for the function at entry."""
    seen, calls, tails, indirect = set(), set(), set(), []
    guarded = set()
    todo = [entry]
    end = BASE + len(img)
    while todo:
        pc = todo.pop()
        while BASE <= pc < end and pc not in seen and len(seen) < limit:
            ins = one(img, pc)
            if ins is None:
                indirect.append(('undecodable', pc)); break
            seen.add(pc)
            nxt = pc + ins.size
            m = ins.mnemonic
            ops = ins.operands
            if m in ('bl',):
                calls.add(ops[0].imm); pc = nxt; continue
            if m == 'blx':
                indirect.append(('blx', pc)); pc = nxt; continue
            if m in ('b', 'b.w') or (m.startswith('b') and len(m) in (3, 5) and m[1:3] in ('eq','ne','hs','lo','mi','pl','vs','vc','hi','ls','ge','lt','gt','le','cs','cc') ):
                tgt = ops[0].imm
                if ins.cc in (A.ARM_CC_AL, A.ARM_CC_INVALID) and m in ('b', 'b.w'):
                    # unconditional: tail call if far outside or to a known function start? treat as jump
                    if tgt < entry - 0x400 or tgt > pc + 0x1000:
                        tails.add(tgt); break
                    pc = tgt; continue
                todo.append(tgt); pc = nxt; continue
            if m in ('cbz', 'cbnz'):
                todo.append(ops[1].imm); pc = nxt; continue
            if m in ('bx',):
                if ops[0].reg == A.ARM_REG_LR:
                    if pc in guarded: pc = nxt; continue
                    break
                indirect.append(('bx', pc)); break
            if m in ('pop', 'pop.w', 'ldm', 'ldm.w', 'ldmia.w', 'ldr.w') and any(o.type == A.ARM_OP_REG and o.reg == A.ARM_REG_PC for o in ops):
                if pc in guarded: pc = nxt; continue
                break
            if m in ('tbb', 'tbh'):
                indirect.append((m, pc)); break
            if m.startswith('it'):
                slot = nxt
                for _ in range(len(m) - 1):
                    guarded.add(slot)
                    slot += one(img, slot).size
                pc = nxt; continue
            if any(o.type == A.ARM_OP_REG and o.reg == A.ARM_REG_PC for o in ops[:1]) and m.startswith(('mov', 'add', 'ldr')):
                indirect.append(('pcwrite', pc)); break
            pc = nxt
    return seen, calls, tails, indirect

def graph(img, roots, limit_funcs=2000):
    funcs = {}
    todo = list(roots)
    while todo and len(funcs) < limit_funcs:
        f = todo.pop()
        if f in funcs: continue
        info = explore(img, f)
        funcs[f] = info
        for c in info[1] | info[2]:
            if c not in funcs: todo.append(c)
    return funcs

def reach(funcs, root):
    out, todo = set(), [root]
    while todo:
        f = todo.pop()
        if f in out or f not in funcs: continue
        out.add(f)
        todo.extend(funcs[f][1] | funcs[f][2])
    return out

def containing(funcs, addr):
    return [f for f, info in funcs.items() if addr in info[0]]

def control_accesses(img, funcs, base=0x20000308):
    """Track the stock literal-loaded control pointer through each routine.

    This is a direct-reference audit, not a proof about arbitrary computed
    pointers. The stock input hash and executed enqueue/consumer tests pin the
    exact code this audit describes.
    """
    accesses=set()
    for info in funcs.values():
        registers={}
        for at in sorted(info[0]):
            ins=one(img,at);ops=ins.operands;m=ins.mnemonic
            if m.startswith('ldr') and len(ops)==2 and ops[1].type==A.ARM_OP_MEM and ops[1].mem.base==A.ARM_REG_PC:
                registers[ops[0].reg]=word(img,((at+4)&~3)+ops[1].mem.disp)
                continue
            if m.startswith(('ldr','str')) and ops and ops[-1].type==A.ARM_OP_MEM:
                operand=ops[-1].mem
                if registers.get(operand.base)==base:
                    accesses.add((at,'store' if m.startswith('str') else 'load',operand.disp))
            if ops and ops[0].type==A.ARM_OP_REG and not m.startswith(('str','cmp','tst','push','b','cb')):
                registers.pop(ops[0].reg,None)
    return sorted(accesses)
