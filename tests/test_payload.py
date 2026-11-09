import pathlib,sys,struct,importlib.util
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
import capstone
import payload as p
base=0x180000000;entry=0x200000;flag=0x210000;obj=0x100000;parent=0x101000;cell=0x102000;vm=0x104000;string=0x106000;stack=0x308008;sentinel=0x220000
regs=[UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11,UC_X86_REG_R14,UC_X86_REG_RDI,UC_X86_REG_RBX]
def test(kind='preview',name=b'@placeholder_foldgroup',enabled=True,match=True,chain=True,model=True,tracked=False):
 u=Uc(UC_ARCH_X86,UC_MODE_64)
 for a,n in [(0x100000,0x10000),(entry,0x1000),(flag,0x1000),(sentinel,0x1000),(0x300000,0x10000),((base+p.HOOK_RVA)&~4095,0x2000),(base+0x5d5000,0x1000)]:u.mem_map(a,n)
 def q(a,v):u.mem_write(a,struct.pack('<Q',v))
 u.mem_write(base+0x5d5570,b'\xc3');u.mem_write(entry,p.payload(base,flag));u.mem_write(flag,bytes([enabled]));q(flag+64,parent if tracked else 0);q(stack,sentinel)
 q(parent+16,0);q(parent+0x28,0x10f800);u.mem_write(0x10f808,b'\x00\x80');q(obj+8,0x107000);q(0x107000+16,parent if chain else 0);q(parent+8,0x108000);q(0x108000+16,cell)
 q(cell+0x260,obj if kind=='avatar' and match else 0);q(cell,base+p.CELL_VT);q(cell+0x290,obj if kind in ['preview','avatar'] and match else 0);q(cell+0x298,obj if kind=='badge' and match else 0);q(cell+0x2f0,vm if model else 0)
 q(cell+0x268,0x109000);q(0x109008,0x10a000);q(0x10a010,0x10b000);q(0x10b028,0x10c000);q(0x10b008,0x10d000);q(0x10d010,0x10e000);q(0x10e028,0x10f000);u.mem_write(0x10c018,struct.pack('<iii',0,0,16));u.mem_write(0x10f018,struct.pack('<iii',14,0,50));q(vm+0x160,string);q(vm+0x170,len(name));q(vm+0x178,31);u.mem_write(string,name)
 u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_RSP,stack);u.reg_write(UC_X86_REG_EFLAGS,0x246)
 before={r:0x100+i*0x10 for i,r in enumerate(regs)}
 for r,v in before.items():u.reg_write(r,v)
 stopped=[]
 def hook(uc,a,n,data):
  if a==base+0x5d5570:
   assert uc.reg_read(UC_X86_REG_RCX)==parent
   assert uc.reg_read(UC_X86_REG_RDX)==(0 if enabled and name==b'@placeholder_foldgroup' else 1)
   assert uc.reg_read(UC_X86_REG_RSP)%16==8
  if a in [sentinel,base+p.HOOK_RVA+12]:stopped.append(a);uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(entry,0,count=500)
 center=enabled and match and chain and model and name==b'@placeholder_foldgroup' and kind=='avatar'
 expect=enabled and match and chain and model and name==b'@placeholder_foldgroup' and kind!='avatar'
 assert stopped==[sentinel if expect else base+p.HOOK_RVA+12],(kind,stopped)
 for r,v in before.items():assert u.reg_read(r)==v,(r,u.reg_read(r),v)
 assert u.reg_read(UC_X86_REG_RSP)==(stack+8 if expect else stack-104)
 assert struct.unpack('<QQ',u.mem_read(flag+8,16))==((1,0) if expect and kind=='preview' else (0,1) if expect else (0,0))
 assert struct.unpack('<i',u.mem_read(0x10c018,4))[0]==0
 assert struct.unpack('<i',u.mem_read(0x10c020,4))[0]==16
 return 1
cases=[dict(kind='avatar',enabled=False,tracked=True),dict(kind='avatar',name=b'normal-chat',tracked=True),dict(kind='avatar'),dict(kind='avatar',enabled=False),dict(kind='avatar',name=b'normal-chat'),{},dict(kind='badge'),dict(enabled=False),dict(name=b'@placeholder_stickyfolder'),dict(name=b'@placeholder_foldgrouq'),dict(match=False),dict(chain=False),dict(model=False)]
print('Emulation cases passed:',sum(test(**x) for x in cases))
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
pathlib.Path('dist').mkdir(exist_ok=True)
pathlib.Path('dist/payload-disassembly.txt').write_text('\n'.join(f'{x.address:x} {x.mnemonic} {x.op_str}' for x in md.disasm(p.payload(base,flag),entry)))
print('Payload bytes:',len(p.payload(base,flag)))
