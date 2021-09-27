# -*- mode: python -*-
from pathlib import Path
import os
root= os.path.join(str(Path.home()),'Shared/home_speed_detector')
a = Analysis([root+'/src/speed-cam.py'],
             pathex=[root+'/home_speed_detector_Installers/Deb64'],
	     datas=[(root+'/src/logging.conf','.')],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
	  a.zipfiles,
          a.datas,
	  name='VehicleSpeedDetector',
          debug=False,
          strip=None,
          upx=True,
          console=True )

