Home speed detector Installer scripts
The home_speed_detector installer scripts enable you to create single file executables for the collection of Python scripts and the necessary interpreter and requisites. 
The executables are created using the Python module, PyInstaller so this will need to be in your Python environment.
The installers are necessarily very platform-dependent - you can only create an executable for your current platform. 
PyInstaller uses .spec files to define paths, target directories etc. and you should read the PyInstaller docs for details. 
I have provided spec files  with source and target file paths as examples. These willl need to be changed to match your installation.
I have also provided batch files for Windows and bash shell files for Linux that launch the installer process, the paths in these will also need to be amended to suit your installation. 
I recommend using a virtual environment for running the scripts, mine are called Win_py36_env and Lin_py36_env, so you will need to change these as well.

 
