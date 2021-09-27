# -*- mode: python -*-
from pathlib import Path
import os
root= os.path.join(str(Path.home()),'home_speed_detector')
#dict_tree=Tree(root+'/AROW_V2/AROWSendV2/AROWSend/src/web',prefix='web/')
a = Analysis([root+'speed-cam.py'],
             pathex=[root+'/PyInstallers/Deb64/home_speed_detector'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
	  a.zipfiles,
          a.datas,
	  dict_tree,
	  name='VehicleSpeedDetector',
          debug=False,
          strip=None,
          upx=True,
          console=True )

