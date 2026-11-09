"""Build the standalone Windows application; does not include Weixin DLL files."""
from pathlib import Path
import PyInstaller.__main__
root=Path(__file__).resolve().parent
PyInstaller.__main__.run([
 str(root/'portable_app.py'),'--name','WeixinFoldedChatPatch','--onefile','--windowed','--clean','--noconfirm',
 '--distpath',str(root/'dist/portable'),'--workpath',str(root/'dist/pyinstaller-work'),'--specpath',str(root/'dist'),
 '--collect-binaries','capstone',
 '--add-data',str(root/'build_fixed_patch.py')+';.',
 '--add-data',str(root/'installer')+';installer',
 '--add-data',str(root/'docs/fixed-patch.md')+';docs',
])
