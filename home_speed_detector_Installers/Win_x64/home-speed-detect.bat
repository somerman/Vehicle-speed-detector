ECHO OFF
ECHO Batch file for home_speed-detector on 64-bit Windows as one file
Z:\WinPy3864_venv\Scripts\PyInstaller %CD%\home-speed-detect_install_folder.spec ^
--distpath=%CD%\Windows64Executables ^
--workpath=%~d0%\PyInstall ^
--clean
ECHO Done
PAUSE
