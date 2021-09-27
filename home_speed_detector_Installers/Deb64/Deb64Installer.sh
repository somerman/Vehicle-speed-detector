#!/bin/bash
echo "Script for home_speed_detector installer on 64-bit Deb using Python3.6"

installer_path=$HOME/Shared/home_speed_detector/home_speed_detector_Installers
#echo $installer_path
#run the installer spec
$HOME/Shared/Lin_py36_env/bin/pyinstaller $installer_path/Deb64/home_speed_detect_install.spec --distpath=$installer_path/Deb64/Deb64Executables --workpath=$HOME/Shared/PyInstall --clean
cp  $HOME/Shared/home_speed_detector/src/config.ini $installer_path/Deb64/Deb64Executables
read -p "Finished..." ok
