import sys,pathlib,struct,hashlib,json,importlib.util,collections
import argparse,os,shutil
import pefile,capstone
import payload as p
ap=argparse.ArgumentParser(description='Build a patch from your own exact-version Weixin.dll; does not install it.')
ap.add_argument('--dll',type=pathlib.Path,default=pathlib.Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Tencent'/'Weixin'/'4.2.0.13'/'Weixin.dll')
ap.add_argument('--out',type=pathlib.Path,default=pathlib.Path('dist/fixed-patch'))
args=ap.parse_args();source=args.dll;original=source.read_bytes();
if hashlib.sha256(original).hexdigest()!=p.EXPECTED:raise SystemExit('Unsupported original DLL hash; no patch built.')
pe=pefile.PE(data=original,fast_load=True);base=pe.OPTIONAL_HEADER.ImageBase;fa=pe.OPTIONAL_HEADER.FileAlignment;sa=pe.OPTIONAL_HEADER.SectionAlignment
align=lambda x,a:(x+a-1)//a*a
code_rva=align(pe.OPTIONAL_HEADER.SizeOfImage,sa);data_rva=code_rva+sa
code=p.payload(base,base+data_rva);detour=b'\x48\xb8'+struct.pack('<Q',base+code_rva)+b'\xff\xe0'
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);md.detail=True;locations=[p.HOOK_RVA+2]
for ins in md.disasm(code,base+code_rva):
 if ins.mnemonic=='movabs' and len(ins.operands)==2 and ins.operands[1].type==capstone.x86.X86_OP_IMM:
  val=ins.operands[1].imm
  if base<=val<base+data_rva+8192:locations.append(ins.address-base+ins.size-8)
assert len(locations)>=7,locations
blocks=collections.defaultdict(list)
for r in locations:blocks[r&~4095].append(0xa000|(r&4095))
extra=bytearray()
for page,values in sorted(blocks.items()):
 if len(values)%2:values.append(0)
 extra+=struct.pack('<II',page,8+len(values)*2)+struct.pack('<'+'H'*len(values),*values)
reloc=pe.OPTIONAL_HEADER.DATA_DIRECTORY[5];reloc_bytes=pe.get_data(reloc.VirtualAddress,reloc.Size)+extra
body=bytearray(4096);body[0]=1;body[32:48]=b'WXFOLD-UI-V1\0\0\0\0';body+=reloc_bytes
code_raw=align(len(original),fa);data_raw=code_raw+align(len(code),fa)
b=bytearray(original);b.extend(b'\0'*(code_raw-len(b)));b+=code;b+=b'\0'*(data_raw-len(b));b+=body;b+=b'\0'*(align(len(b),fa)-len(b))
new_headers=pe.sections[-1].get_file_offset()+40;assert new_headers+80<=pe.sections[0].PointerToRawData
for i,(name,rva,vsize,raw,rsize,chars) in enumerate([(b'.wxui',code_rva,len(code),code_raw,align(len(code),fa),0x60000020),(b'.wxdata',data_rva,len(body),data_raw,align(len(body),fa),0xc0000040)]):
 b[new_headers+i*40:new_headers+(i+1)*40]=struct.pack('<8sIIIIIIHHI',name.ljust(8,b'\0'),vsize,rva,rsize,raw,0,0,0,0,chars)
fh=pe.FILE_HEADER.get_file_offset();oh=pe.OPTIONAL_HEADER.get_file_offset()
struct.pack_into('<H',b,fh+2,len(pe.sections)+2);struct.pack_into('<I',b,oh+4,pe.OPTIONAL_HEADER.SizeOfCode+align(len(code),fa));struct.pack_into('<I',b,oh+8,pe.OPTIONAL_HEADER.SizeOfInitializedData+align(len(body),fa));struct.pack_into('<I',b,oh+56,align(data_rva+len(body),sa))
# Move the relocation table to the new data section and extend it with absolute operands.
struct.pack_into('<II',b,reloc.get_file_offset(),data_rva+4096,len(reloc_bytes))
security=pe.OPTIONAL_HEADER.DATA_DIRECTORY[4];struct.pack_into('<II',b,security.get_file_offset(),0,0)
o=pe.get_offset_from_rva(p.HOOK_RVA);assert b[o:o+12]==p.ORIGINAL;b[o:o+12]=detour
struct.pack_into('<I',b,oh+64,0)
out=args.out;out.mkdir(parents=True,exist_ok=True)
patched=out/'Weixin.UI-patched.dll';patched.write_bytes(b)
import ctypes as C,ctypes.wintypes as W
checksum=C.WinDLL('imagehlp').MapFileAndCheckSumW;checksum.argtypes=[W.LPCWSTR,C.POINTER(W.DWORD),C.POINTER(W.DWORD)];checksum.restype=W.DWORD
header=W.DWORD();computed=W.DWORD();assert checksum(str(patched.resolve()),C.byref(header),C.byref(computed))==0
struct.pack_into('<I',b,oh+64,computed.value);patched.write_bytes(b)
assert checksum(str(patched.resolve()),C.byref(header),C.byref(computed))==0 and header.value==computed.value
backup=out/'Weixin.original.dll'
if not backup.exists():backup.write_bytes(original)
assert hashlib.sha256(backup.read_bytes()).hexdigest()==p.EXPECTED
final=pefile.PE(data=b,fast_load=True);assert final.FILE_HEADER.NumberOfSections==14;assert final.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size==0
# Exercise relocation at a different ASLR base and compare every generated instruction.
delta=0x700000000000;relocated=bytearray(b)
for r in locations:
 off=final.get_offset_from_rva(r);v=struct.unpack_from('<Q',relocated,off)[0];struct.pack_into('<Q',relocated,off,v+delta)
assert relocated[code_raw:code_raw+len(code)]==p.payload(base+delta,base+delta+data_rva)
assert relocated[o:o+12]==b'\x48\xb8'+struct.pack('<Q',base+delta+code_rva)+b'\xff\xe0'
manifest={'version':'4.2.0.13','original_sha256':p.EXPECTED,'patched_sha256':hashlib.sha256(b).hexdigest(),'hook_rva':hex(p.HOOK_RVA),'code_rva':hex(code_rva),'data_rva':hex(data_rva),'new_relocations':[hex(x) for x in locations],'new_sections':{'.wxui':'read/execute','.wxdata':'read/write'},'checksum_verified':True,'aslr_relocation_verified':True,'signature':'unsigned (original certificate directory removed)','startup_tested':False}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps(manifest,indent=2))



for name in ['Manage-FixedPatch.ps1','Install-FixedPatch.cmd','Restore-Original.cmd']:
 shutil.copyfile(pathlib.Path(__file__).parent/'installer'/name,out/name)
shutil.copyfile(pathlib.Path(__file__).parent/'docs'/'fixed-patch.md',out/'README.md')
print('Build complete. No installed Weixin files or processes were changed.')
