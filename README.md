# home_speed_detector
The home_speed_detection set of python scripts is designed to log vehicle numbers and speeds
using a camera and image recognition to track vehicles. The resultant information can be used to
inform local safety groups, councils and law enforcement of particular traffic issues, or to log traffic
flows when some roadworks, diversions or permanent re-routing takes place.
Based on work originally by Claude Pageau , https://github.com/pageauc/rpi-speed-
camera/tree/master/, Ronit Sinha, https://github.com/ronitsinha/speed-detector, and many others
including of course the OpenCV project and team.
The program works by capturing images on a camera perpendicular to, at a distance from and at an
elevation to, a single or dual track road.
![Optional Text](../docs/images/houseicon.png)
The field of view, shown as the red bounding rectangle is a known size in pixels, and a calibration is
performed to relate pixel spacing to actual length dimensions. Then by tracking the object
horizontally, recording the pixel shift distance and the time taken, object speed can be calculated.
