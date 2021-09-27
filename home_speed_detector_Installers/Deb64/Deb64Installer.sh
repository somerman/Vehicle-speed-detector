#!/bin/bash
echo "Script for home_speed_detector installer on 64-bit Deb using Python3.6"
#run the installer spec
$HOME/Shared/Lin_py36_env/bin/pyinstaller $HOME/Shared/home_speed_detector/home_speed_detector_Installers/Deb64/home_speed_detector.spec --distpath=$HOME/Shared/home_speed_detector/home_speed_detector_Installers/Deb64/Deb64Executables/home_speed_detector --workpath=$HOME/Shared/PyInstall --clean
read -p "Finished..." ok
