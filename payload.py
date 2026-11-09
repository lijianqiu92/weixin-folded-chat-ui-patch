"""Version-specific x64 display filter. This module never opens or modifies a process."""
EXPECTED="afe3d02c58bada3c35009c0cd58ee1f57b2a00fe53237d0dce649107fddb9a20"
HOOK_RVA=0x1e8d3f0
CELL_VT=0x9c8c5c8
ORIGINAL=bytes.fromhex("41565657534883ec484889ce")
import struct

class Code:
 def __init__(self):self.b=bytearray();self.labels={};self.fix=[]
 def emit(self,h):self.b.extend(bytes.fromhex(h))
 def imm(self,h,n):self.emit(h);self.b.extend(struct.pack('<Q',n))
 def label(self,s):self.labels[s]=len(self.b)
 def j(self,op,s):self.emit(op);self.fix.append((len(self.b),s));self.b.extend(b'\0'*4)
 def finish(self):
  for o,s in self.fix:struct.pack_into('<i',self.b,o,self.labels[s]-o-4)
  return bytes(self.b)
def payload(base,flag):
 c=Code();c.emit('9c50524150415141524153') # flags and volatile registers
 # Disabled filtering still restores the preview container if this patch hid it.
 c.emit('4989c84989cb41b910000000');c.imm('48b8',base+CELL_VT)
 c.label('loop');c.emit('4d85c0');c.j('0f84','original');c.emit('493900');c.j('0f84','cell')
 c.emit('4d8b40084d85c0');c.j('0f84','original');c.emit('4d8b401041ffc9');c.j('0f85','loop');c.j('e9','original')
 c.label('cell');c.emit('31d24d3b9860020000');c.j('0f84','identity');c.emit('ba010000004d3b9890020000');c.j('0f84','identity')
 c.emit('ba020000004d3b9898020000');c.j('0f85','original')
 c.label('identity');c.emit('4d8b90f00200004d85d2');c.j('0f84','notfold')
 c.emit('4d8d926001000049837a1016');c.j('0f85','notfold');c.emit('49837a1810');c.j('0f82','notfold')
 c.emit('4d8b124d85d2');c.j('0f84','notfold')
 s=b'@placeholder_foldgroup'
 c.imm('48b8',int.from_bytes(s[:8],'little'));c.emit('493902');c.j('0f85','notfold')
 c.imm('48b8',int.from_bytes(s[8:16],'little'));c.emit('49394208');c.j('0f85','notfold')
 c.emit('41817a10'+s[16:20].hex());c.j('0f85','notfold');c.emit('6641817a14'+s[20:22].hex());c.j('0f85','notfold')
 c.imm('48b8',flag);c.emit('803800');c.j('0f84','notfold')
 c.emit('85d2');c.j('0f84','center')
 c.imm('48b8',flag);c.emit('48ff04d0');c.j('e9','skip')
 c.label('center')
 c.emit('4d8b90900200004d8b52084d8b5210')
 c.imm('48b8',flag);c.emit('4c395040');c.j('0f84','hide')
 c.emit('498b522866f742080080');c.j('0f84','original')
 c.emit('4c895040')
 c.label('hide');c.emit('31d2');c.j('e9','visibility')
 c.label('notfold');c.emit('85d2');c.j('0f85','original')
 c.emit('4d8b90900200004d8b52084d8b5210')
 c.imm('48b8',flag);c.emit('4c395040');c.j('0f85','original')
 c.emit('48c7404000000000ba01000000')
 c.label('visibility')
 # Call Qt on its own painting thread; save volatile vector registers and align the call.
 c.emit('514881ec88000000')
 for i in range(6):c.emit('f30f7f'+bytes([0x44+i*8,0x24,32+i*16]).hex())
 c.emit('4c89d1');c.imm('48b8',base+0x5d5570);c.emit('ffd0')
 for i in range(6):c.emit('f30f6f'+bytes([0x44+i*8,0x24,32+i*16]).hex())
 c.emit('4881c48800000059')
 c.imm('48b8',flag);c.emit('48ff4018');c.j('e9','original')
 restore='415b415a415941585a589d'
 c.label('original');c.emit(restore);c.emit(ORIGINAL.hex());c.imm('48b8',base+HOOK_RVA+len(ORIGINAL));c.emit('ffe0')
 c.label('skip');c.emit(restore+'c3');return c.finish()
