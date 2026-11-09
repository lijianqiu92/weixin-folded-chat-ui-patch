"""Weixin 4.2.0.13: reversible in-memory rendering filter. Standard library only."""
import argparse,ctypes as C,ctypes.wintypes as W,hashlib,json,pathlib,struct,sys,time
K=C.WinDLL('kernel32',use_last_error=True);N=C.WinDLL('ntdll')
EXPECTED='afe3d02c58bada3c35009c0cd58ee1f57b2a00fe53237d0dce649107fddb9a20'
HOOK_RVA=0x1e8d3f0; CELL_VT=0x9c8c5c8; ORIGINAL=bytes.fromhex('41565657534883ec484889ce')
STATE=pathlib.Path(__file__).with_name('weixin-ui-runtime-state.json')
def api(lib,name,args,restype):
 f=getattr(lib,name);f.argtypes=args;f.restype=restype;return f
api(K,'OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
api(K,'CloseHandle',[W.HANDLE],W.BOOL)
api(K,'ReadProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL)
api(K,'WriteProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL)
api(K,'VirtualAllocEx',[W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD,W.DWORD],C.c_void_p)
api(K,'VirtualProtectEx',[W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD,C.POINTER(W.DWORD)],W.BOOL)
api(K,'FlushInstructionCache',[W.HANDLE,C.c_void_p,C.c_size_t],W.BOOL)
api(K,'CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE)
api(K,'OpenThread',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
api(K,'GetThreadContext',[W.HANDLE,C.c_void_p],W.BOOL)
api(N,'NtSuspendProcess',[W.HANDLE],C.c_long);api(N,'NtResumeProcess',[W.HANDLE],C.c_long)
class MOD(C.Structure):
 _fields_=[('dwSize',W.DWORD),('moduleId',W.DWORD),('pid',W.DWORD),('globalCount',W.DWORD),('processCount',W.DWORD),('base',C.c_void_p),('size',W.DWORD),('hModule',W.HMODULE),('name',W.WCHAR*256),('path',W.WCHAR*260)]
class PROC(C.Structure):
 _fields_=[('dwSize',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',C.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('name',W.WCHAR*260)]
class THREAD(C.Structure):
 _fields_=[('dwSize',W.DWORD),('usage',W.DWORD),('tid',W.DWORD),('pid',W.DWORD),('priority',W.LONG),('delta',W.LONG),('flags',W.DWORD)]
for name,typ in [('Module32',MOD),('Process32',PROC)]:
 for action in ['FirstW','NextW']:api(K,name+action,[W.HANDLE,C.POINTER(typ)],W.BOOL)
for action in ['First','Next']:api(K,'Thread32'+action,[W.HANDLE,C.POINTER(THREAD)],W.BOOL)
def snapshot(flag,typ,first,next_,pid=0):
 s=K.CreateToolhelp32Snapshot(flag,pid)
 if s==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
 try:
  t=typ();t.dwSize=C.sizeof(t);ok=first(s,C.byref(t))
  while ok:
   yield typ.from_buffer_copy(t);ok=next_(s,C.byref(t))
 finally:K.CloseHandle(s)
def module(pid):
 for m in snapshot(0x18,MOD,K.Module32FirstW,K.Module32NextW,pid):
  if m.name.lower()=='weixin.dll':return m.base,m.size,m.path
 raise RuntimeError('Weixin.dll not found in target process')
def select_pid():
 ps=[p for p in snapshot(2,PROC,K.Process32FirstW,K.Process32NextW) if p.name.lower()=='weixin.exe'];ids={p.pid for p in ps};roots=[p.pid for p in ps if p.parent not in ids]
 if len(roots)!=1:raise RuntimeError('Cannot select one Weixin main process; use --pid')
 return roots[0]
def read(h,a,n):
 d=C.create_string_buffer(n);got=C.c_size_t()
 if not K.ReadProcessMemory(h,a,d,n,C.byref(got)) or got.value!=n:raise C.WinError(C.get_last_error())
 return d.raw

def write(h,a,data):
 buf=C.create_string_buffer(data);n=C.c_size_t()
 if not K.WriteProcessMemory(h,a,buf,len(data),C.byref(n)) or n.value!=len(data):raise C.WinError(C.get_last_error())

def protect(h,a,n,p):
 old=W.DWORD()
 if not K.VirtualProtectEx(h,a,n,p,C.byref(old)):raise C.WinError(C.get_last_error())
 return old.value

from payload import payload

def install_bytes(h,address,new,expected):
 # Freeze briefly, verify that no thread is executing inside the overwritten prologue,
 # then write and verify. Always resume, including on failure.
 if N.NtSuspendProcess(h)<0:raise RuntimeError('Cannot suspend target safely')
 try:
  for t in snapshot(4,THREAD,K.Thread32First,K.Thread32Next):
   if t.pid!=TARGET_PID:continue
   th=K.OpenThread(0x8,False,t.tid)
   if not th:raise RuntimeError('Cannot inspect target thread')
   try:
    raw=C.create_string_buffer(1248);ptr=(C.addressof(raw)+15)&~15
    C.c_uint32.from_address(ptr+48).value=0x100001
    if not K.GetThreadContext(th,ptr):raise C.WinError(C.get_last_error())
    rip=C.c_uint64.from_address(ptr+248).value
    if address<=rip<address+len(new):raise RuntimeError('A thread is in the patch region; retry later')
   finally:K.CloseHandle(th)
  if read(h,address,len(expected))!=expected:raise RuntimeError('Original code mismatch; nothing written')
  old=protect(h,address,len(new),0x40)
  try:
   try:
    write(h,address,new)
    if read(h,address,len(new))!=new:raise RuntimeError('Patch verification failed')
   except Exception:
    write(h,address,expected);K.FlushInstructionCache(h,address,len(expected));raise
   K.FlushInstructionCache(h,address,len(new))
  finally:protect(h,address,len(new),old)
 finally:
  if N.NtResumeProcess(h)<0:raise RuntimeError('Could not resume target process')

def state_for_process(h,pid,base):
 if not STATE.exists():return None
 s=json.loads(STATE.read_text(encoding='utf-8'))
 if s['pid']!=pid or s['base']!=base:return None
 addr=base+HOOK_RVA
 if read(h,addr,12)!=bytes.fromhex(s['detour']):return None
 if read(h,s['allocation']+32,16)!=b'WXFOLD-UI-V1\0\0\0\0':return None
 return s

def run():
 global TARGET_PID
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['enable','disable','status']);ap.add_argument('--pid',type=int);args=ap.parse_args()
 if C.sizeof(C.c_void_p)!=8:raise RuntimeError('Use 64-bit Python')
 TARGET_PID=args.pid or select_pid();base,size,path=module(TARGET_PID)
 if hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('Unsupported Weixin.dll hash; no writes performed')
 h=K.OpenProcess(0xC38,False,TARGET_PID)
 if not h:raise C.WinError(C.get_last_error())
 try:
  s=state_for_process(h,TARGET_PID,base)
  if args.action=='status':
   if not s:print(json.dumps({'installed':False,'pid':TARGET_PID}));return
  elif args.action=='disable':
   if not s:print('No matching runtime patch is active.');return
   write(h,s['allocation'],b'\0')
  elif s:write(h,s['allocation'],b'\1')
  else:
   if read(h,base+HOOK_RVA,len(ORIGINAL))!=ORIGINAL:raise RuntimeError('Hook bytes differ; aborting')
   allocation=K.VirtualAllocEx(h,None,8192,0x3000,4)
   if not allocation:raise C.WinError(C.get_last_error())
   code=payload(base,allocation);entry=allocation+4096
   write(h,allocation,b'\0'*32+b'WXFOLD-UI-V1\0\0\0\0');write(h,entry,code);protect(h,entry,4096,0x20);K.FlushInstructionCache(h,entry,len(code))
   detour=b'\x48\xb8'+struct.pack('<Q',entry)+b'\xff\xe0'
   s={'pid':TARGET_PID,'base':base,'allocation':allocation,'entry':entry,'detour':detour.hex(),'dll_sha256':EXPECTED}
   # Persist rollback coordinates before connecting the hook, with filtering disabled.
   STATE.write_text(json.dumps(s,indent=2),encoding='utf-8')
   install_bytes(h,base+HOOK_RVA,detour,ORIGINAL)
   write(h,allocation,b'\1')
  enabled=read(h,s['allocation'],1)!=b'\0';counts=struct.unpack('<QQ',read(h,s['allocation']+8,16))
  print(json.dumps({'installed':True,'enabled':enabled,'pid':TARGET_PID,'preview_paint_skipped':counts[0],'badge_paint_skipped':counts[1],'program_files_modified':False}))
 finally:K.CloseHandle(h)
if __name__=='__main__':
 try:run()
 except Exception as e:print('ERROR:',str(e),file=sys.stderr);sys.exit(1)

