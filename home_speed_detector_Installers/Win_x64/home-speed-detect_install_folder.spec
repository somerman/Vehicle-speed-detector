# -*- mode: python -*-
from pathlib import Path
root = 'Z:\\home_speed_detector'
a = Analysis([root+'/src/speed-cam.py'],
             pathex=[root+'/home_speed_detector_Installers/Deb64'],
	     datas=[(root+'/src/logging.conf','.'),(root+'/Overlays/*.ini','Overlays')],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
	  #a.zipfiles,
          #a.datas,
	  name='VehicleSpeedDetector',
          debug=False,
          strip=None,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
	      
               strip=None,
               upx=True,
               name='home_speed_detector')


