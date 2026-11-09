"""Portable GUI; public EXE contains patch tools, never Weixin program files."""
import argparse,contextlib,hashlib,io,json,os,pathlib,queue,runpy,subprocess,sys,threading
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
import pefile,capstone,payload,runtime_patch
VERSION='0.1.0-preview'
PATCHED='095b058a672774b1107595dfcdc1c1e3b3879b8363429d1564d5b975dbca2f24'
ASSETS=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parent))
HOME=pathlib.Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else pathlib.Path(__file__).resolve().parent
DATA=HOME/'data'/'fixed-patch'
TARGET=pathlib.Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Tencent'/'Weixin'/'4.2.0.13'/'Weixin.dll'
def digest(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def build(source,out):
 previous=sys.argv[:]
 try:
  sys.argv=[str(ASSETS/'build_fixed_patch.py'),'--dll',str(source),'--out',str(out)]
  with contextlib.redirect_stdout(io.StringIO()) as log:runpy.run_path(str(ASSETS/'build_fixed_patch.py'))
  return log.getvalue()
 finally:sys.argv=previous

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--gui-check',action='store_true');ap.add_argument('--self-check',action='store_true');ap.add_argument('--check-build',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path);ap.add_argument('--report',type=pathlib.Path);args=ap.parse_args()
 if args.self_check or args.check_build:
  result={'version':VERSION,'python_bundled':bool(getattr(sys,'frozen',False)),'required_assets_present':all((ASSETS/x).exists() for x in ['build_fixed_patch.py','installer/Manage-FixedPatch.ps1','docs/fixed-patch.md']),'weixin_binaries_bundled':False}
  if args.check_build:
   if not args.out:raise SystemExit('--check-build requires --out')
   build(args.check_build,args.out);result['built_sha256']=digest(args.out/'Weixin.UI-patched.dll');result['build_verified']=result['built_sha256']==PATCHED
   if not result['build_verified']:raise RuntimeError('Built DLL mismatch')
  if args.report:args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  elif sys.stdout:print(json.dumps(result))
  return
 root=tk.Tk();
 if args.gui_check:root.withdraw()
 root.title('微信折叠聊天 UI 补丁 · '+VERSION);root.geometry('690x530');root.minsize(610,480)
 style=ttk.Style(root);style.configure('TButton',padding=9);style.configure('TLabel',font=('Microsoft YaHei UI',10))
 frame=ttk.Frame(root,padding=20);frame.pack(fill='both',expand=True)
 ttk.Label(frame,text='微信「折叠的聊天」显示补丁',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w')
 ttk.Label(frame,text='隐藏红点和消息预览 · 标题居中 · 仅支持 4.2.0.13 精确版本',wraplength=640).pack(anchor='w',pady=(8,6))
 ttk.Label(frame,text='固定版需退出微信；手动版不需退出。备份保存在本工具旁的 data 文件夹。\n这是预览版；更新或重装覆盖程序文件后可能失效。',wraplength=640).pack(anchor='w',pady=(0,12))
 buttons=ttk.Frame(frame);buttons.pack(fill='x');q=queue.Queue();controls=[]
 text=tk.Text(frame,height=13,wrap='word',font=('Microsoft YaHei UI',9),state='disabled');text.pack(fill='both',expand=True,pady=12)
 def log(s):q.put(('log',str(s)))
 def job(fn):
  for b in controls:b.configure(state='disabled')
  def run():
   try:fn()
   except BaseException as e:log('操作未完成：'+str(e))
   finally:q.put(('done',None))
  threading.Thread(target=run,daemon=True).start()
 def poll():
  try:
   while True:
    k,s=q.get_nowait()
    if k=='done':
     for b in controls:b.configure(state='normal')
    else:text.configure(state='normal');text.insert('end',s+'\n');text.see('end');text.configure(state='disabled')
  except queue.Empty:pass
  root.after(100,poll)
 def status():
  if not TARGET.exists():log('没有在默认位置找到微信 DLL。');return
  h=digest(TARGET)
  log('当前程序：'+('固定补丁已安装' if h==PATCHED else '原版，可应用补丁' if h==payload.EXPECTED else '不支持的版本或文件，拒绝修改'))
  log('本工具原版备份：'+('完整' if (DATA/'Weixin.original.dll').exists() and digest(DATA/'Weixin.original.dll')==payload.EXPECTED else '尚未生成/不可用'))
 def launch(mode):
  ps=pathlib.Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
  log('已打开安装/恢复窗口。请查看该窗口的提示；工具不会强制退出微信。')
  process=subprocess.Popen([str(ps),'-NoLogo','-NoProfile','-File',str(DATA/'Manage-FixedPatch.ps1'),'-Mode',mode],creationflags=subprocess.CREATE_NEW_CONSOLE)
  process.wait();status()
 def fixed():
  if not TARGET.exists():raise RuntimeError('未找到默认位置的 Weixin.dll')
  if digest(TARGET)==PATCHED:log('固定补丁已经安装，无需重复操作。');return
  log('正在校验原文件并生成补丁与备份……')
  build(TARGET,DATA);log('构建和备份校验完成。');launch('Install')
 def restore():
  if not (DATA/'Weixin.original.dll').exists():raise RuntimeError('本工具目录没有原版备份。请使用最初安装时的恢复工具。')
  if digest(DATA/'Weixin.original.dll')!=payload.EXPECTED:raise RuntimeError('原版备份校验不匹配')
  launch('Restore')
 def temporary(action):
  (HOME/'data').mkdir(exist_ok=True);runtime_patch.STATE=HOME/'data'/'weixin-ui-runtime-state.json';prior=sys.argv[:]
  try:
   sys.argv=['runtime_patch.py',action]
   with contextlib.redirect_stdout(io.StringIO()) as out:runtime_patch.run()
   log(out.getvalue().strip());log('手动模式只对本次微信进程生效；完整退出后清除。')
  finally:sys.argv=prior
 actions=[('检查状态',status),('安装固定版',fixed),('恢复原版',restore),('手动启用本次微信',lambda:temporary('enable')),('关闭手动补丁',lambda:temporary('disable'))]
 for i,(label,fn) in enumerate(actions):
  b=ttk.Button(buttons,text=label,command=lambda f=fn:job(f));b.grid(row=i//3,column=i%3,sticky='ew',padx=3,pady=3);controls.append(b)
 for col in range(3):buttons.columnconfigure(col,weight=1)
 def close():
  if any(str(b.cget('state'))=='disabled' for b in controls):messagebox.showinfo('正在操作','请等当前操作和安装窗口结束后再关闭。');return
  root.destroy()
 root.protocol('WM_DELETE_WINDOW',close)
 if args.gui_check:
  root.update_idletasks()
  result={'gui_constructed':True,'action_buttons':len(controls),'tk_version':tk.TkVersion}
  root.destroy()
  if args.report:args.report.write_text(json.dumps(result),encoding='utf-8')
  return
 poll();job(status);root.mainloop()
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if '--report' in sys.argv:
   try:pathlib.Path(sys.argv[sys.argv.index('--report')+1]).write_text(json.dumps({'error':str(e)}),encoding='utf-8')
   except Exception:pass
  raise
