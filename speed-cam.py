#!/usr/bin/env python
"""
Based on speed-cam.py written by Claude Pageau
Windows, Unix, Raspberry (Pi) - python opencv2 Speed tracking
using picamera module, Web Cam or RTSP IP Camera
Claude' original GitHub Repo here https://github.com/pageauc/rpi-speed-camera/tree/master/

    This is a python openCV object speed tracking demonstration program.
    It will detect speed in the field of view and use openCV to calculate the
    largest contour and return its x,y coordinate.  Multiple images are tracked for
    a specific number of frames average speed of all samples  is calculated with a variance.
    Note: Application variables a json file, user values in an ini file

    Installation
    ------------
    You can use a Raspberry Pi with a RPI camera module or  a pc and Web Cam installed and working
    or Windows, Linux Distro .
    See the docs for detailed setup, there are a lot of variables that contribute to accuracy and 
    integrity, some of which interact. Users can set these outside of the program in (multiple)
    ini files for each setup. Default values are used unless overridden by user configs.
    
    
Rewritten by Simon Banks to refactor into classes and transfer/split  config values, configparser and json , 
splitting program variables from user variables, improve the accuracy of tracking and add functionality. 
RTFM. 
Use Python 3 - no really, just do it.
"""

progVer = "1.00"  # current version of this python script

from json.decoder import JSONDecodeError
import os
# Get information about this script including name, launch path, etc.
# This allows script to be renamed or relocated to another directory
mypath = os.path.abspath(__file__)  # Find the full path of this python script
# get the path location only (excluding script name)
baseDir = mypath[0:mypath.rfind("/")+1]
baseFileName = mypath[mypath.rfind("/")+1:mypath.rfind(".")]
progName = os.path.basename(__file__)
horiz_line = "----------------------------------------------------------------------"
print(horiz_line)
print("%s %s  home vehicle tracking" % (progName, progVer))
print("Motion track largest moving object and calculate speed .")
print(horiz_line)
print("Loading  Wait ...")
import time
import datetime
import sys
#import glob
#import shutil
import logging
import logging.config
import logging.handlers
import sqlite3
from threading import Thread
import subprocess
import numpy as np
from array import array
import json
import PySimpleGUI as sg
#import defaults
import speed_file_utils
import queue
from speed_constants import Speed_Colours as colours, Speed_Errors as errors, Speed_Constants as constants
from statistics import mean, pstdev
import math
import copy
from speed_sql_db import SpeedDB
from os import path

"""
Check for config.ini variable file to import and warn if not Found.
Overlay status logging is not available yet since the overlay name variable from config is needed before
setting up logging for the overlay instance
"""
from config import *
# there are two loggers, the overall app and the instance of the selected overlay ( if any)
try:
    #get the application logger setup from the conf file
    app_log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logging.conf')
    logging.config.fileConfig(app_log_file_path)
    appLogger=logging.getLogger('appLogger')
except Exception as e:
    pass
# import user settings and program settings
cfg=Config(baseDir,appLogger)

# fix rounding problems with picamera resolution
camera_width = (cfg.CAMERA_WIDTH + 31) // 32 * 32
camera_height = (cfg.CAMERA_HEIGHT + 15) // 16 * 16

# Now that variables are imported from config.ini, set up Logging since we have overlay path
# we could put different formatting for the file and console messaging
fileFormatter = logging.Formatter('%(asctime)s:%(levelname)-8s: %(funcName)-8s: %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
consoleFormatter = logging.Formatter('%(asctime)s %(levelname)-8s %(funcName)-10s: %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S' )
#create the handlers that will be attached to the overlay logger
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(logging.DEBUG)
consoleHandler.setFormatter(consoleFormatter)
# set up the overlay logging file handler with limitation on log size option
overlay_log_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 OVERLAYS_DIR,cfg.overlayName+'.log')
fileHandler=logging.handlers.RotatingFileHandler(overlay_log_path,
                                                 maxBytes=cfg.maxLogSize,
                                                 backupCount=cfg.logBackups)
fileHandler.setFormatter(fileFormatter)
#create a logger specific to the overlay
overlayLogger=logging.getLogger(cfg.overlayName +'Logger')
overlayLogger.propagate = 0

if cfg.loggingToFile:# add console and file handling
    overlayLogger.addHandler(fileHandler)
    if cfg.verbose:
        overlayLogger.addHandler(consoleHandler)
elif cfg.verbose: #just console and all messages
    consoleHandler.setLevel(logging.DEBUG)
    overlayLogger.addHandler(consoleHandler)
else: # just console but only critical messages
    consoleHandler.setLevel(logging.CRITICAL)
    overlayLogger.addHandler(consoleHandler)
 
# Do a quick check to see if the sqlite database directory path exists
db_dir_path = os.path.join(baseDir, cfg.DB_DIR)
if not os.path.exists(db_dir_path):  # Check if database directory exists
    os.makedirs(db_dir_path)         # make directory if Not Found
db_path = os.path.join(db_dir_path, cfg.DB_NAME)   # Create path to db file

global image_path 

# import a single variable from the search_config.py file
# This is done to auto create a media/search directory
"""
try:
    from search_config import search_dest_path
except ImportError:
    search_dest_path = 'media/search'
    appLogger.warn("Problem importing search_dest_path variable")
    appLogger.info("Setting default value search_dest_path = %s", search_dest_path)
"""
      
    
# import the necessary packages
# -----------------------------
try:   # Check to see if opencv is installed
    import cv2
except ImportError:
    appLogger.error("Could Not import cv2 library")
    if sys.version_info > (2, 9):
        appLogger.error("python3 failed to import cv2")
        appLogger.error("Try installing opencv for python3")
        appLogger.error("For RPI See https://github.com/pageauc/opencv3-setup")
    else: # can't continue
        appLogger.error("python2 failed to import cv2")
        appLogger.error("Try RPI Install per command")
        appLogger.error("%s %s Exiting Due to Error", progName, progVer)
    sys.exit(1)
    
try:  #Add this check in case running on non RPI platform using web cam
    from picamera.array import PiRGBArray
    from picamera import PiCamera
except ImportError:
    webcam = True

if not webcam:
    # Check that pi camera module is installed and enabled
    cam_result = subprocess.check_output("vcgencmd get_camera", shell=True)
    cam_result = cam_result.decode("utf-8")
    cam_result = cam_result.replace("\n", "")
    if (cam_result.find("0")) >= 0:   # -1 is zero not found. Cam OK
        overlayLogger.error("Pi Camera Module Not Found %s", cam_result)
        overlayLogger.error("if supported=0 Enable Camera per command sudo raspi-config")
        overlayLogger.error("if detected=0 Check Pi Camera Module is Installed Correctly")
        overlayLogger.error("%s %s Exiting Due to Error", progName, progVer)
        sys.exit(1)
    else:
        overlayLogger.info("Pi Camera Module is Enabled and Connected %s", cam_result)



# fix possible invalid values when resizing
if cfg.window_bigger < 0.1:
    cfg.window_bigger = 0.1
if cfg.image_bigger < 0.1:
    cfg.image_bigger = 0.1

webcam_flipped = False
if webcam:
    # Check if Web Cam image flipped in any way
    if (cfg.WEBCAM_HFLIP or cfg.WEBCAM_VFLIP):
        webcam_flipped = True

quote = '"'  # Used for creating quote delimited log file of speed data
            
class SpeedCam(object):
    def __init__(self):
        self.speed_units= None
        #self.road=self.get_settings()
        self.get_speed_units()

    def get_speed_units(self):
        # Calculate conversion from camera pixel width to actual speed.
        self.px_to_kph_L2R = float(cfg.cal_obj_mm_L2R/cfg.cal_obj_px_L2R * 0.0036)
        self.px_to_kph_R2L = float(cfg.cal_obj_mm_R2L/cfg.cal_obj_px_R2L * 0.0036)

        if cfg.SPEED_MPH:
            self.speed_units = "mph"
            self.speed_conv_L2R = 0.621371 * self.px_to_kph_L2R
            self.speed_conv_R2L = 0.621371 * self.px_to_kph_R2L
        else:
            self.speed_units = "kph"
            self.speed_conv_L2R = self.px_to_kph_L2R
            self.speed_conv_R2L = self.px_to_kph_R2L 
    
    
#------------------------------------------------------------------------------
class PiVideoStream:
    def __init__(self, resolution=(camera_width, camera_height),
                 framerate=cfg.CAMERA_FRAMERATE, rotation=0,
                 hflip=cfg.CAMERA_HFLIP, vflip=cfg.CAMERA_VFLIP):
        """ initialize the camera and stream """
        try:
            self.camera = PiCamera()
        except:
            overlayLogger.error("PiCamera Already in Use by Another Process")
            overlayLogger.error("%s %s Exiting Due to Error", progName, progVer)
            sys.exit(1)
        self.camera.resolution = resolution
        self.camera.rotation = rotation
        self.camera.framerate = framerate
        self.camera.hflip = hflip
        self.camera.vflip = vflip
        self.rawCapture = PiRGBArray(self.camera, size=resolution)
        self.stream = self.camera.capture_continuous(self.rawCapture,
                                                     format="bgr",
                                                     use_video_port=True)

        """
        initialize the frame and the variable used to indicate
        if the thread should be stopped
        """
        self.thread = None
        self.frame = None
        self.stopped = False

    def start(self):
        """ start the thread to read frames from the video stream """
        self.thread = Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        return self

    def update(self):
        """ keep looping infinitely until the thread is stopped """
        for f in self.stream:
            # grab the frame from the stream and clear the stream in
            # preparation for the next frame
            self.frame = f.array
            self.rawCapture.truncate(0)

            # if the thread indicator variable is set, stop the thread
            # and resource camera resources
            if self.stopped:
                self.stream.close()
                self.rawCapture.close()
                self.camera.close()
                return

    def read(self):
        """ return the frame most recently read """
        return self.frame

    def stop(self):
        """ indicate that the thread should be stopped """
        self.stopped = True
        if self.thread is not None:
            self.thread.join()

#------------------------------------------------------------------------------
class WebcamVideoStream:
    def __init__(self, CAM_SRC=cfg.WEBCAM_SRC, CAM_WIDTH=cfg.WEBCAM_WIDTH,
                 CAM_HEIGHT=cfg.WEBCAM_HEIGHT,saveStream=False,isFile=False, isLoop =True):
        """
        initialize the video camera stream and read the first frame
        from the stream
        """
        self.vs_thread = None
        self.saveStream=saveStream# for calibration use
        self.isFile=isFile
        self.src = CAM_SRC
        self.cam_stream = cv2.VideoCapture(self.src)
        self.stream_start_time= time.time()
        
        if not isFile:
            self.cam_stream.set(3, CAM_WIDTH)
            self.cam_stream.set(4, CAM_HEIGHT)
            (self.grabbed, self.frame) = self.cam_stream.read()
            if self.grabbed :# the camera may not be connected
                self.fps=self.__get_initial_fps(self.cam_stream)
        else:
            self.fps= self.cam_stream.get(cv2.CAP_PROP_FPS)
            self.grabbed=True# fake this
            self.stream_start_time=os.path.getctime(self.src)
            self.isLoop=isLoop
        if saveStream:
            savefilename= cfg.overlayName+"_calibrate.mp4"
            fourccCode = cv2.VideoWriter_fourcc(*'mp4v')# for avi use XDIV codec
            self.vw=self._open_writer(fourcc=fourccCode,strfilename=savefilename)
            

    def start(self):
        """ start the thread to read frames from the video stream """
        self.q=queue.Queue(24)# create a queue buffer to smooth out processing blips
        self.stopped = False # used to indicate that the thread should  be stopped 
    
        self.vs_thread = Thread(target=self.update, args=())
        self.vs_thread.daemon = True
        self.vs_thread.start()
        return self

    def update(self):
        """ keep looping infinitely until the thread is stopped """
        frame_count=0
        self.fps_start_time=time.time()
        while not self.stopped:
            # if the thread indicator variable is set, stop the thread
            #if self.stopped:
                #self.cam_stream.release()
                #return
            # otherwise, read the next frame from the stream
            (self.grabbed, self.frame) = self.cam_stream.read()
            #check for valid frames
            if not self.grabbed:
                if self.isFile:
                    self.cam_stream.release()
                    if self.isLoop:
                        self.cam_stream = cv2.VideoCapture(self.src)# loop to beginning
                    #self.cam_stream.set(cv2.CAP_PROP_POS_FRAMES,0)
                else: # no live frames received, then safely exit
                    self.stopped = True #maybe camera has failed
            else: # add the frame and timestamp (since stream start) to a queue
                self.q.put((self.frame,(self.stream_start_time+(self.cam_stream.get(cv2.CAP_PROP_POS_MSEC)/1000))))# convert to seconds for compatibility
                if self.saveStream:
                    self._write(self.frame)
                frame_count=self.get_latest_fps(frame_count)
                
        self.cam_stream.release()    #release resources

    def read(self):
        """ return the frame from the buffering queue
        Although you can flip the frame, it takes resources so its better to invert the camera.            
        """
        #buffering the frame reads in the queue allows a smoother replay if resources are limited.
        frame= None
        if not self.q.empty():
            #print("Queue", self.q.qsize())
            frame=self.q.get()
            if webcam_flipped:
                if (cfg.WEBCAM_HFLIP and cfg.WEBCAM_VFLIP):
                    frame = cv2.flip(frame, -1)
                elif cfg.WEBCAM_HFLIP:
                    frame = cv2.flip(frame, 1)
                elif cfg.WEBCAM_VFLIP:
                    frame = cv2.flip(frame, 0)
        return frame
        
    def stop(self):
        """ indicate that the thread should be stopped """
        self.stopped = True
        if self.saveStream:
            self._close_writer()
        # wait until stream resources are released (producer thread might be still grabbing frame)
        if self.vs_thread is not None:
            self.vs_thread.join(2.0)  # properly handle thread exit

    def isOpened(self):
        return self.cam_stream.isOpened()

    def __get_initial_fps(self,cam):
        """Provides an estimate of the actual frame rate being received"""
        # Start time
        num_frames = 120
        start = time.time()

		# Grab a few frames
        for i in range(0, num_frames):
            ret, frame = cam.read()

		# End time]
        end = time.time()

		# Time elapsed
        seconds = end - start
        overlayLogger.debug("Time taken : {0} seconds".format(seconds))

		# Calculate frames per second
        fps = num_frames / seconds
        period= 1/fps *1000
        overlayLogger.info("Estimated frames per second : %.2f period :%.2f mS",fps,period)
        return fps
      
    def get_latest_fps(self, frame_count):
        """ Calculate and display frames per second processing """
        #fps=0
        if frame_count >= 300:
            duration = float(time.time() - self.fps_start_time)
            self.fps = float(frame_count / duration)
            if cfg.log_fps ==True:
                overlayLogger.info("Reading at %.2f fps over last %i frames", self.fps, frame_count)

            frame_count = 0
            self.fps_start_time = time.time()# reset time for next count
        else:
            frame_count += 1
        return frame_count
    
    
    
    def _open_writer(self,fourcc,strfilename,fps=30,imgsize=(640,352)):
        self.videoWriter=cv2.VideoWriter(strfilename,fourcc,fps,imgsize)    
        return self.videoWriter

    def _write(self,frame):
        if self.videoWriter is None:
            return
        self.videoWriter.write(frame)

    def _close_writer(self):
        self.videoWriter.release()
        
        
#------------------------------------------------------------------------------


def init_settings():
    """Initialize and Display program variable settings from config.ini"""
    global image_path
    appLogger.info("Application start")
        
    current_working_directory = os.getcwd()
    html_path = "media/html"
    image_path=os.path.join(cfg.image_path,cfg.overlayName)
    if not os.path.isdir(image_path):
        overlayLogger.info("Creating Image Storage Folder %s", image_path)
        os.makedirs(image_path)
    os.chdir(image_path)
    os.chdir(current_working_directory)
    #not supported in this version
    """
    if imageRecentMax > 0:
        if not os.path.isdir(imageRecentDir):
            overlayLogger.info("Create Recent Folder %s", imageRecentDir)
            try:
                os.makedirs(imageRecentDir)
            except OSError as err:
                overlayLogger.error('Failed to Create Folder %s - %s',
                              imageRecentDir, err)
    
    
    if not os.path.isdir(search_dest_path):
        overlayLogger.info("Creating Search Folder %s", search_dest_path)
        os.makedirs(search_dest_path)
    
    if not os.path.isdir(html_path):
        overlayLogger.info("Creating html Folder %s", html_path)
        os.makedirs(html_path)
    
    os.chdir(current_working_directory)
    """
    if cfg.verbose:
        print(horiz_line)
        print("Note: To Send Full Output to File Use command")
        print("python -u ./%s | tee -a log.txt" % progName)
        print("Set log_data_to_file=True to Send speed_Data to CSV File %s.log"
              % baseFileName)
        print(horiz_line)
        print("")
        print("Debug Messageds .. verbose=%s  display_fps=%s calibrate=%s"
              % (cfg.verbose, cfg.log_fps, cfg.calibrate))
        print("                  show_out_range=%s" % cfg.show_out_range)
        print("Overlays ......... overlayEnable=%s  overlayName=%s"
              % (cfg.overlayEnable, cfg.overlayName))
        print("Calibration ..... cal_obj_px_L2R=%i px  cal_obj_mm_L2R=%i mm  speed_conv_L2R=%.5f"
              % (cfg.cal_obj_px_L2R, cfg.cal_obj_mm_L2R, rc.speed_conv_L2R))
        print("                  cal_obj_px_R2L=%i px  cal_obj_mm_R2L=%i mm  speed_conv_R2L=%.5f"
              % (cfg.cal_obj_px_R2L, cfg.cal_obj_mm_R2L, rc.speed_conv_R2L))
        if cfg.overlayEnable:
            print("                  (Change Settings in %s)" % cfg.overlayPath)
        else:
            print("                  (Change Settings in %s)" % cfg.configFilePath)
        print("Logging ......... Log_data_to_CSV=%s  log_filename=%s.csv (CSV format)"
              % (cfg.log_data_to_CSV, baseFileName))
        #print("                  loggingToFile=%s  logFilePath=%s"
         #     % (cfg.loggingToFile, cfg.logFilePath))
        print("                  SQLITE3 DB_PATH=%s  DB_TABLE=%s"
              % (db_path, cfg.DB_TABLE))
        print("Speed Trigger ... Log only if max_speed_over > %i %s"
              % (cfg.max_speed_over, rc.speed_units))
        print("                  and track_counter >= %i consecutive motion events"
              % cfg.track_counter)
        print("Exclude Events .. If  x_diff_min < %i or x_diff_max > %i px"
              % (cfg.x_diff_min, cfg.x_diff_max))
        print("                  If  y_upper < %i or y_lower > %i px"
              % (y_upper, y_lower))
        print("                  or  x_left < %i or x_right > %i px"
              % (x_left, x_right))
        print("                  If  max_speed_over < %i %s"
              % (cfg.max_speed_over, rc.speed_units))
        #print("                  If  event_timeout > %.2f seconds Start New Track"
         #     % (cfg.event_timeout))
        print("                  track_timeout=%.2f sec wait after Track Ends"
              " (avoid retrack of same object)"
              % (cfg.track_timeout))
        print("Speed Photo ..... Size=%ix%i px  image_bigger=%.1f"
              "  rotation=%i  VFlip=%s  HFlip=%s "
              % (image_width, image_height, cfg.image_bigger,
                 cfg.CAMERA_ROTATION, cfg.CAMERA_VFLIP, cfg.CAMERA_HFLIP))
        print("                  image_path=%s  image_Prefix=%s"
              % (image_path, cfg.image_prefix))
        print("                  image_font_size=%i px high  image_text_bottom=%s"
              % (cfg.image_font_size, cfg.image_text_bottom))
        print("                  image_jpeg_quality=%s  image_jpeg_optimize=%s"
              % (cfg.image_jpeg_quality, cfg.image_jpeg_optimize))
        print("Motion Settings . Size=%ix%i px  px_to_kph_L2R=%f  px_to_kph_R2L=%f speed_units=%s"
              % (camera_width, camera_height, rc.px_to_kph_L2R, rc.px_to_kph_R2L, rc.speed_units))
        print("                  CAM_LOCATION= %s" % cfg.CAM_LOCATION)
        print("                  WINDOW_BIGGER=%i gui_window_on=%s"
              " (Display OpenCV Status Windows on GUI Desktop)"
              % (cfg.window_bigger, cfg.gui_window_on))
        print("                  CAMERA_FRAMERATE=%i fps video stream speed"
              % cfg.CAMERA_FRAMERATE)
        print("Sub-Directories . imageSubDirMaxHours=%i (0=off)"
              "  imageSubDirMaxFiles=%i (0=off)"
              % (cfg.imageSubDirMaxHours, cfg.imageSubDirMaxFiles))
        #print("                  imageRecentDir=%s imageRecentMax=%i (0=off)"
             #% (imageRecentDir, imageRecentMax))
        if cfg.spaceTimerHrs > 0:   # Check if disk mgmnt is enabled
            print("Disk Space  ..... Enabled - Manage Target Free Disk Space."
                  " Delete Oldest %s Files if Needed" % (cfg.spaceFileExt))
            print("                  Check Every spaceTimerHrs=%i hr(s) (0=off)"
                  "  Target spaceFreeMB=%i MB  min is 100 MB)"
                  % (cfg.spaceTimerHrs, cfg.spaceFreeMB))
            print("                  If Needed Delete Oldest spaceFileExt=%s  spaceMediaDir=%s"
                  % (cfg.spaceFileExt, cfg.spaceMediaDir))
        else:
            print("Disk Space  ..... Disabled - spaceTimerHrs=%i"
                  "  Manage Target Free Disk Space. Delete Oldest %s Files"
                  % (cfg.spaceTimerHrs, cfg.spaceFileExt))
            print("                  spaceTimerHrs=%i (0=Off)"
                  " Target spaceFreeMB=%i (min=100 MB)" % (cfg.spaceTimerHrs, cfg.spaceFreeMB))
        print("")
        print(horiz_line)
    return


#------------------------------------------------------------------------------

#------------------------------------------------------------------------------

def logging_notifications():
    if cfg.overlayEnable:
        appLogger.info("Overlay Enabled per overlayName=%s", cfg.overlayName)
    else:
        appLogger.info("Overlay Disabled per overlayEnable=%s", cfg.overlayEnable)

    if cfg.verbose:
        if cfg.loggingToFile:
            print("Logging to File %s and Console" % overlay_log_path)
           #print("Logging to File %s and Console" % cfg.logFilePath)
        else:
            overlayLogger.info("Logging to Console only")

        if cfg.gui_window_on:
            appLogger.info("To quit,press q on GUI window or ctrl-c in this terminal")
            
        else:
            appLogger.info("To quit,press ctrl-c in this terminal ")
    else:
        print("Logging Messages Disabled per verbose=%s" % cfg.verbose)

    if cfg.calibrate:
        overlayLogger.warn("IMPORTANT: Camera Is In Calibration Mode ....")

    overlayLogger.debug("Begin Motion Tracking .....")
#----------------------------------------------------------------------------------------------------
class Vehicle(object):
    """Creates object to hold separate vehicle properties"""
    def __init__(self,x,y,w,h,centroid, dir,found_area,frame):
        self.track_list=[] # list of tracking co-ordinates etc. 
        self.track_record=self.TrackRecord(x,y,w,h,centroid,dir,found_area,frame )
        self.cur_track_x = x
        self.cur_track_y = y
        self.prev_track_x=x
        self.prev_track_y=y
        
        self.track_w = w  # movement width of object contour
        self.track_h = h  # movement height of object contour
        self.biggest_area = found_area
        self.cur_track_time = frame[1]
        self.speed_list=[]
        self.travel_direction=None
        self._add_tracking_record(self.track_record)
        self.active=True
        self.FinalSpeed=0
        self.StdDev=0
        
    def _add_tracking_record(self,track ):
        
        self.track_list.append(track)
        if len(self.track_list)>1:
            self.track_list[-1].prev_track_x=self.track_list[-2].cur_track_x#hold the old values
            self.track_list[-1].prev_track_y= self.track_list[-2].cur_track_y
        self.cur_track_x= track.cur_track_x
        self.cur_track_y= track.cur_track_y
        self.cur_track_time= track.track_time
        
    def _remove_tracking_record(self,pos):
        try:
            self.track_list.pop(pos)
        except:
            pass
        
    def clear_tracking_list(self):
        
        self.track_list.clear()

    def _get_tracking_record(self,pos):
        return self.track_list[pos]

    class TrackRecord(object):
        def __init__(self,x,y,w,h,centroid,dir,found_area,frame):
            if x==0:# there is a state when direction is unknown, but is actually left to right
                x=x+w #in this mode we want to track the rh edge of the contour, so add the width to the x pos. 
            #N.B. this state can also occur when very large objects track r2l, so the x position reaches zero. 
            #But this is rare and we just have to suck it up.It will invalidate the track position.
            self.cur_track_x = x
            self.cur_track_y = y
            self.prev_track_x=x
            self.prev_track_y=y
            self.track_w = w  # movement width of object contour
            self.track_h = h  # movement height of object contour
            self.centroid=centroid
            self.biggest_area = found_area
            self.track_time = frame[1]
            self.direction=dir
            
#------------------------------------------------------------------------------
class SpeedTrack(object):
    #TODO this class is too big and needs breaking down
    def __init__(self,isFile, rect,image_path):
        self.is_file_src=isFile
        self.ave_speed = 0.0
        self.frame_count = 0
        self.first_event = True   # Start a New Motion Track
        self.vehicle_start_pos_x = 0
        self.vehicle_end_pos_x = 0
        self.vehicle_prev_pos_x = 0
        #self.travel_direction = None
        self.event_timer = None
        self.last_frame_seen=0
        self. track_count = 0
        #self.speed_list = []
        self.speed_path = image_path
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.lastSpaceCheck = datetime.datetime.now()
        self.prev_start_time=0
        self.track_start_time=0
        self.fps_time = time.time()
        self.speed_db=None
        self.vehicles=[] # to hold a list of vehicles being tracked
        self.skip_frames=0# used to prevent dual tracking
        self.x_left=rect[0]
        self.x_right=rect[1]
        self.y_upper=rect[2]
        self.y_lower=rect[3]

        
        self.kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (10, 10))
        self.kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (6, 6))
        #self.Prev_Frame=np.empty([0,0,0])
        # Calculate position of text on the images
        if cfg.image_text_bottom:
            self.text_y = (image_height - 50)  # show text at bottom of image
        else:
            self.text_y = 10  # show text at top of image
        self.speed_tracker()
        
    def speed_tracker(self):
        """ Main speed tracking processing function """
        # Initialize prev_image used for taking speed image photo
        if cfg.log_data_to_DB:
            self.speed_db=SpeedDB( db_path)
        logging_notifications()
        rd=FoVDrawer("jeff")
        mask_rect=rd.load_mask()
        if mask_rect is not None:
            self.x_left=mask_rect[0]
            self.x_right= mask_rect[0]+mask_rect[2]
            self.y_upper = mask_rect[1]
            self.y_lower=mask_rect[1]+mask_rect[3]
                
        # Warn user of performance hit if webcam image flipped
        if (webcam and webcam_flipped):
            overlayLogger.warn("Recommend you do NOT Flip Webcam stream")
            overlayLogger.warn("Otherwise SLOW streaming Will Result...")
            overlayLogger.warn("If necessary physically flip camera and")
            overlayLogger.warn("Set config.py WEBCAM_HFLIP and WEBCAM_VFLIP to False")
        mainwin='Movement (q Quits)'
        cv2.namedWindow(mainwin)# create a window to hold the main image
        cv2.moveWindow(mainwin, 1900,-900)
        #self.contourwin="Contours"
        #cv2.namedWindow(self.contourwin)
        #cv2.moveWindow(self.contourwin, xwin-400,ywin)
        # initialize a cropped grayimage1 image
        grayimage1=self.get_init_image()
        
        still_scanning = True
        if image_sign_on:
            image_sign_bg = np.zeros((image_sign_resize[0], image_sign_resize[1], 4))
            image_sign_view = cv2.resize(image_sign_bg, (image_sign_resize))
            image_sign_view_time = time.time()
        veh=None
        
        while still_scanning:  # process camera thread images and calculate speed
            #if we need to wait for eg vehicles to clear after counting, this reduces dual counting
                
            frame=vs.read()# Read frame data from video steam thread instance
            if frame is not None:
                image2 = frame[0] # extract image from tuple
                
                #process the frame for contours within the cropped area
                if self.skip_frames == 0:    
                    grayimage1, contours = self.speed_get_contours(image2, grayimage1)
                    # if contours found, find the one with biggest area
                    # the assumption is that the vehicle is the largest object in the frame
                    if contours:
                        total_contours = len(contours)
                        orphan_contours=[]
                        #biggest_area = MIN_AREA
                        contour_count=0
                        valid_contours=0
                        for contour in contours:
                            #new_veh=False    
                            contour_count+=1
                            valid_contour = False
                            
                            # get area of contour
                            if self.validate_contour(contour) ==errors.ERROR_SUCCESS:
                                valid_contour=True
                                valid_contours+=1
                                    
                            if valid_contour :
                                found_area = cv2.contourArea(contour)
                                (x, y, w, h) = cv2.boundingRect(contour)
                                centroid = self.get_centroid(x, y, w, h)
                                # now find closest track match in existing vehicles ( if any)
                                if len(self.vehicles) > 0 :
                                
                                    for veh in self.vehicles:
                                        ret=self._check_centroid_dist(veh, centroid)# is this valid and belonging to this vehicle?

                                        if ret == errors.ERROR_X_SHIFT_TOO_LARGE or ret== errors.ERROR_Y_SHIFT_TOO_LARGE:
                                            #if not (any((contour== cont).all() for cont in orphan_contours)):#avoid duplicates
                                            try:
                                                for cont in orphan_contours:
                                                    if contour ==cont:#avoid duplicates
                                                        continue
                                                    else:
                                                        orphan_contours.append(contour)#add to a temp list
                                            except Exception as e: 
                                                overlayLogger.error("contour error",e)
                                                continue
                                            #break
                                        if ret== errors.ERROR_SUCCESS:
                                            try:
                                                if len(orphan_contours) >0:
                                                    cont=orphan_contours.pop(-1)# found contour match so  remove entry    
                                                dir=self._get_direction(veh,centroid)
                                                isSameDir= self._check_direction(veh,centroid)
                                                if isSameDir:# its the same way so add another record
                                                    #if self._check_x_dist(veh,x) != errors.ERROR_SUCCESS:
                                                        #continue
                                                    if veh.active:
                                                        if dir=="L2R":
                                                            x=x+w
                                                            if x>=self.x_right-self.x_left:# the width of the cropped area
                                                                continue #hit the end so don't add
                                                        else:
                                                            if x<=0:# assume the start of cropped area x is 0
                                                                continue
                                                        veh._add_tracking_record(Vehicle.TrackRecord(x,y,w,h,centroid,dir,found_area,frame))
                                                    break # found it so we can skip other vehicles
                                            except Exception as e:
                                                continue    
                                        if ret== errors.ERROR_X_SHIFT_TOO_SMALL:
                                            continue # the contour is identical            
                                else: # the first one
                                    dir=None
                                    veh=Vehicle(x,y,w,h,centroid,dir,found_area,frame)#assign id to vehicle
                                    dir=self._get_direction(veh,centroid)
                                    if dir=="L2R":# we want the rh side of the contour to be tracked
                                        veh.track_list[-1].cur_track_x=x+w
                                    veh.track_list[-1].direction=dir
                                    self.last_frame_seen = frame[1]
                                    self.first_event = True
                                    self.vehicles.append(veh)
                                            
                                self.process_motion_events(veh,total_contours,frame)

                                if cfg.gui_window_on:
                                    # show small circle at contour xy if required
                                    if SHOW_CIRCLE:
                                        cv2.circle(image2,
                                                (int(veh.cur_track_x + self.x_left * cfg.window_bigger),
                                                int(veh.cur_track_y + self.y_upper * cfg.window_bigger)),
                                                CIRCLE_SIZE, colours.cvGreen, LINE_THICKNESS)
                                    if SHOW_RECTANGLE:
                                        # otherwise a rectangle around most recent contour
                                        cv2.rectangle(image2,
                                                    (int(self.x_left + veh.cur_track_x),
                                                    int(self.y_upper + veh.cur_track_y)),
                                                    (int(self.x_left + veh.cur_track_x + veh.track_w),
                                                    int(self.y_upper + veh.cur_track_y + veh.track_h)),
                                                    colours.cvRed, LINE_THICKNESS)
                        if len(orphan_contours) >0:#new vehicle?
                                    self.vehicles.append(Vehicle(x,y,w,h,centroid,None,found_area,frame))#
                                    orphan_contours.pop(-1)# remove last entry    
                        if valid_contours==0:
                            self.vehicles.clear()
                else:#skip frames
                    self.skip_frames-=1 # this will be caught at zero
                if cfg.gui_window_on:
                    #cv2.imshow('Difference Image',difference image)
                    image2 = self.speed_image_add_lines(image2, colours.cvRed)
                    image2= self.create_cal_lines(image2)
                    image_view = cv2.resize(image2, (image_width, image_height))
                    if cfg.gui_show_camera:
                        cv2.imshow(mainwin, image_view)
                    if cfg.show_thresh_on:
                        cv2.imshow('Threshold', differenceimage)
                    if cfg.show_crop_on:
                        image_crop = image2[self.y_upper:self.y_lower, self.x_left:self.x_right]
                        cv2.imshow('Crop Area', image_crop)
                    if image_sign_on:
                        if time.time() - image_sign_view_time > image_sign_timeout:
                            # Cleanup the image_sign_view
                            image_sign_bg = np.zeros((image_sign_resize[0], image_sign_resize[1], 4))
                            image_sign_view = cv2.resize(image_sign_bg, (image_sign_resize))
                        cv2_window_speed_sign = 'Last Average Speed:'
                        cv2.namedWindow(cv2_window_speed_sign, cv2.WINDOW_NORMAL)
                        cv2.cv2.setWindowProperty(cv2_window_speed_sign, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                        cv2.imshow(cv2_window_speed_sign, image_sign_view)
                else:
                    self.vehicles.clear()# no contours so no vehicles
            key= cv2.waitKey(1)
            
            if key == ord('m'):# invoke the mask drawer
                (x1,y1,w1,h1)=cv2.selectROI("Select",image2,False)
                cv2.destroyWindow('Select')
                if w1*h1 ==0:# nothing selected
                    continue
                rd=FoVDrawer("jeff")
                msg="Do you want to save this mask?"
                title = "Please confirm"
                layout = [[sg.Text(msg)],      
                    [sg.Submit(), sg.Cancel()]]      
                window = sg.Window(title, layout)    

                event, values = window.read()    
                window.close()
                if event== 'Submit':
                    rd.save_mask((x1,y1,w1,h1))
                    self.x_left = x1
                    self.x_right=x1+w1
                    self.y_lower =y1+h1
                    self.y_upper=y1
                    grayimage1=self.get_init_image()
                
               
            elif key == ord('q') or key == 27:
                cv2.destroyAllWindows()
                overlayLogger.info("End Motion Tracking ......")
                still_scanning = False
                vs.stop()
                
                break
            if self.is_file_src:
                time.sleep(1.0 / vs.fps)

        raise KeyboardInterrupt()
    
    def speed_image_add_lines(self,image, color):
        cv2.line(image, (self.x_left, self.y_upper),
                (self.x_right, self.y_upper), color, 1)
        cv2.line(image, (self.x_left, self.y_lower),
                (self.x_right, self.y_lower), color, 1)
        cv2.line(image, (self.x_left, self.y_upper),
                (self.x_left, self.y_lower), color, 1)
        cv2.line(image, (self.x_right, self.y_upper),
                (self.x_right, self.y_lower), color, 1)
        return image

    def create_cal_lines(self,cal_image):
        hash_colour = cfg.hash_colour
        motion_win_colour = cfg.motion_win_colour
        for i in range(10, image_width - 9, 10):
            cv2.line(cal_image, (i, int(image_height/2)), (i, int(image_height/2) + 30), hash_colour, 1)
            #cv2.line(cal_image, (i, self.y_upper - 5), (i, self.y_upper + 30), hash_color, 1)
        # This is motion window
        cal_image = self.speed_image_add_lines(cal_image, motion_win_colour)
        return cal_image

    def take_calibration_image(self,speed, filename, cal_image):
        """
        Create a calibration image for determining value of  variable
        Create calibration hash marks
        """
        # If there is bad contrast with background you can change the hash
        # colors to give more contrast.  You need to change values in the ini file
        
        cal_image=self.create_cal_lines(cal_image)
        #for i in range(10, image_width - 9, 10):
         #   cv2.line(cal_image, (i, y_upper - 5), (i, y_upper + 30), hash_colour, 1)
        # This is motion window
        #cal_image = self.speed_image_add_lines(cal_image, motion_win_colour)

        print("----------------------------- Create Calibration Image "
            "-----------------------------")
        print("")
        print("  Instructions for using %s image for camera calibration" % filename)
        print("")
        print("  Note: If there is only one lane then L2R and R2L settings will be the same")
        print("  1 - Use L2R and R2L with Same Size Reference Object, Eg. same vehicle for both directions.")
        print("  2 - For objects moving L2R Record cal_obj_px_L2R Value Using red hash marks at every 10 px. Current setting is %i px" %
            cfg.cal_obj_px_L2R)
        print("  3 - Record cal_obj_mm_L2R of object. This is actual length in mm of object above. Current setting is %i mm" %
            cfg.cal_obj_mm_L2R)
        print("    If recorded speed %.1f %s is too low, increase cal_obj_mm_L2R to adjust or vice-versa" %
            (speed, rc.speed_units))
        print("Repeat calibration with preferably same object moving R2L and update ini R2L variables")
        print("cal_obj_mm_R2L and cal_obj_px_R2L accordingly")
        if cfg.overlayEnable:
            print("  4 - Edit %s File and Change Values for Above Variables." %
                cfg.overlayPath)
        else:
            print("  4 - Edit %s File and Change Values for the Above Variables." %
                cfg.configFilePath)
        print("  5 - Do a speed test to confirm/tune Settings.  You may need to repeat or use the recorded video.")
        print("  6 - When calibration is finished, Set config.ini variable  calibrate = False")
        print("      Then Restart speed-cam.py and monitor activity.")
        print("")
        print("  WARNING: It is advised to Use 320x240 or 640 x 480 stream for best performance.")
        print("           Higher resolutions need more OpenCV processing")
        print("           and may reduce data accuracy and reliability by missing targets.")
        print("")
        print("  Calibration image Saved To %s%s  " % (baseDir, filename))
        print("  ")
        print("")
        print("---------------------- Press cntl-c to Quit  "
            "-----------------------")
        return cal_image


    def get_init_image(self):
        try:
            frame=vs.read() #get frame and timestamp fro videostream thread
            image2 = frame[0]  # extract image info from tuple
            col_processed_img=image2.copy()
        
            # initialise crop image to motion tracking area only
            #cv2.imshow("diff",col_processed_img) #debug
            image_crop = image2[self.y_upper:self.y_lower, self.x_left:self.x_right]
            #cv2.imshow("Cropped", image_crop)#debug
        except Exception as ex:
            vs.stop()
            overlayLogger.warn("Problem Connecting To Camera Stream.")
            overlayLogger.warn("Restarting Camera.  One Moment Please ...")
            time.sleep(4)
            return None
        grayimage1 = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
        return grayimage1
        

    def is_valid_vector(self,veh,vector):
        #deal with the first entry case
        if veh.track_list[-1].vector==None:
            return True
        pass
    
    def validate_contour(self,contour):
        if not self._check_area(contour) :
            return errors.ERROR_AREA_TOO_SMALL  
        #if not self._check_x_bounds(contour):
            #return errors.ERROR_OUT_OF_RANGE  
     
        return errors.ERROR_SUCCESS                                            

    def _get_direction(self,veh:Vehicle,centroid):
        x_pos,ypos=centroid
        x_pos_old=veh.track_list[-len(veh.track_list)].centroid[0]
        #if vehic.travel_direction==None:
                #this is the first time
        if x_pos>x_pos_old:# check the xpos
            #if x_pos - self.vehicle_prev_pos_x > 0:
            travel_direction="L2R"
        elif x_pos==x_pos_old:
            travel_direction=None
        else:
            travel_direction="R2L"
        return travel_direction
        
    def get_centroid(self,x, y, w, h):
        x1 = w // 2
        y1 = h // 2
        return(x+x1, y+y1)
    
    def _check_area(self,contour):
        biggest_area = cfg.MIN_AREA
        found_area = cv2.contourArea(contour)
        if found_area > biggest_area: #filters the contour to avoid small objects 
            return True
        return False    

    def _check_x_bounds(self,contour):
        # x,y is top left of rect
        (x, y, w, h) = cv2.boundingRect(contour)
        # check if object contour is completely within crop area
        # the whole object has to be visible to be counted. This is a problem
        #for large vehicles that may fill the crop area
        #this is the main limitation on detection accuracy, since fast vehicles
        # don't get picked up
        if (x > 1 and (x + w) < (self.x_left+1 )):
            return True
        return False    
    """    
    def _check_timeout(self, event_timer,last_time):
        # Check if last motion event timed out
        reset_time_diff = event_timer-last_time
        #reset_time_diff = time.time() - event_timer
        if  reset_time_diff >= cfg.event_timeout:
            overlayLogger.info("Tracking event_timer %.1f sec Exceeded %.1f sec timeout",
                                            reset_time_diff, cfg.event_timeout)
            return errors.ERROR_TIMEOUT
        return errors.ERROR_SUCCESS                                            
    """
    def _check_centroid_dist(self,veh : Vehicle,centroid):
        if veh==None:
            return errors.ERROR_OUT_OF_RANGE
        if abs(centroid[0]-veh.track_list[-1].centroid[0]) < constants.X_DIFF_MIN:
            return errors.ERROR_X_SHIFT_TOO_SMALL
        if abs(centroid[0]-veh.track_list[-1].centroid[0]) > constants.X_DIFF_MAX:
            return errors.ERROR_X_SHIFT_TOO_LARGE
        if abs(centroid[1]-veh.track_list[-1].centroid[1]) > constants.Y_DIFF_MAX:
            return errors.ERROR_Y_SHIFT_TOO_LARGE
        return errors.ERROR_SUCCESS
        
    
    def _check_x_dist(self,veh,chk_x):
        if veh==None:
            return errors.ERROR_OUT_OF_RANGE
        if abs(chk_x-veh.prev_track_x) < cfg.x_diff_min:
            return errors.ERROR_X_SHIFT_TOO_SMALL
        if abs(chk_x-veh.prev_track_x) > cfg.x_diff_max:
            return errors.ERROR_X_SHIFT_TOO_LARGE
        return errors.ERROR_SUCCESS
     
    def process_motion_events(self,veh,total_contours,frame):
        #image2=frame[0]
        if self.first_event:   # This is a first valid motion event
            self.first_event = False  # Only one first track event
            self.track_start_time = veh.cur_track_time # Record track start time
            self.prev_start_time = veh.cur_track_time
            self.vehicle_start_pos_x = veh.cur_track_x
            self.vehicle_prev_pos_x = veh.prev_track_x
            self.vehicle_end_pos_x = veh.cur_track_x
            overlayLogger.debug("New detection at xy(%i,%i), starting new track 1/%i",
                        veh.cur_track_x, veh.cur_track_y, cfg.track_counter )
            #self.event_timer = time.time() # Reset event timeout
            
            veh.speed_list = []
        else:
            self.vehicle_prev_pos_x = self.vehicle_end_pos_x
            self.vehicle_end_pos_x = veh.cur_track_x
         
            self.track_start_time = veh.cur_track_time # Record track start time
            # check if movement is within acceptable distance range of last event
            if self.check_movement_range(self.prev_start_time, veh, total_contours,frame)==True:
                self.prev_start_time = veh.cur_track_time # hold the current time for next round
            #else:
                #del veh
                
    def _check_direction(self,vehic:Vehicle,centroid):
        if len(vehic.track_list)<=1:
            return True
        x_pos,ypos=centroid
        x_pos_old=vehic.track_list[-1].centroid[0]
        old_dir=vehic.track_list[-1].direction
        #if vehic.travel_direction==None:
                #this is the first time
        if x_pos>x_pos_old:# check the xpos
            #if x_pos - self.vehicle_prev_pos_x > 0:
            travel_direction="L2R"
        else:
            travel_direction="R2L"
         #check for valid direction same as last
        if travel_direction != old_dir:
            return False
        return True
                        
    def check_movement_range(self, prev_start_time, veh :Vehicle, total_contours,frame):
        """ check if movement is within acceptable distance range of last track"""
        image2=frame[0]
        if veh.active==True:
            track_count = len(veh.track_list)
            cur_ave_speed=0
            track_diff=abs(veh.track_list[-1].cur_track_x - veh.track_list[-1].prev_track_x)
            if track_diff > cfg.x_diff_min and track_diff <= cfg.x_diff_max:
            #if (abs(self.vehicle_end_pos_x - self.vehicle_prev_pos_x) > x_diff_min and
             #                       abs(self.vehicle_end_pos_x - self.vehicle_prev_pos_x) <= x_diff_max):
                cur_track_dist = track_diff
                #cur_track_dist = abs(self.vehicle_end_pos_x - self.vehicle_prev_pos_x)
                if veh.cur_track_time==prev_start_time:
                    return False
                try:
                    if  veh.track_list[-1].direction=="L2R":
                        cur_ave_speed = float((abs(cur_track_dist /float(abs(veh.cur_track_time - prev_start_time)))) * rc.speed_conv_L2R)
                        cal_obj_px = cfg.cal_obj_px_L2R
                        cal_obj_mm = cfg.cal_obj_mm_L2R
                    elif  veh.track_list[-1].direction=="R2L":
                        cur_ave_speed = float((abs(cur_track_dist /float(abs(veh.cur_track_time - prev_start_time)))) * rc.speed_conv_R2L)
                        cal_obj_px = cfg.cal_obj_px_R2L
                        cal_obj_mm = cfg.cal_obj_mm_R2L
                    else:
                        return False
                except Exception as e:
                    overlayLogger.error(veh)
                    return False
                veh.speed_list.append(cur_ave_speed)
                ave_speed = np.mean(veh.speed_list)
                prev_start_time = veh.cur_track_time
                #self.event_timer = frame[1]
                            
                if track_count >= cfg.track_counter:

                    tot_track_dist = abs(veh.cur_track_x - self.vehicle_start_pos_x)
                    tot_track_time = abs(veh.cur_track_time-veh.track_list[0].track_time)
                    #ave_speed = float(tot_track_dist /tot_track_time) * rc.speed_conv_R2L
                    # the first tracked speed can be wrong, so discard it
                    veh.speed_list.pop(0)
                    if len(veh.speed_list)>0:
                        ave_speed = mean(veh.speed_list)
                        #variance = pvariance(veh.speed_list,ave_speed)
                        veh.StdDev= pstdev(veh.speed_list)
                        veh.FinalSpeed=ave_speed
                    # Track length exceeded so take process speed photo
                        if cfg.max_speed_count > ave_speed > cfg.max_speed_over :
                        #if cfg.max_speed_count > ave_speed > cfg.max_speed_over or cfg.calibrate:
                        # uncomment for debug
                            overlayLogger.debug("Added- %i/%i xy(%i,%i) %3.1f %s"
                                        " D=%i/%i %i sqpx %s",
                                        track_count, cfg.track_counter,
                                        veh.cur_track_x, veh.cur_track_y,
                                        ave_speed, rc.speed_units,
                                        abs(veh.cur_track_x - self.vehicle_prev_pos_x),
                                        cfg.x_diff_max,
                                        veh.track_list[-1].track_h*veh.track_list[-1].track_w,
                                        veh.track_list[-1].direction)
                    
                            overlayLogger.info("Tracking complete- %s Ave %.1f %s,StdDev %.2f, Tracked %i px in %.3f sec, Calib %ipx %imm  ",
                                    veh.track_list[-1].direction,
                                    ave_speed, rc.speed_units,
                                    veh.StdDev,
                                    tot_track_dist,
                                    tot_track_time,
                                    cal_obj_px,
                                    cal_obj_mm
                                    )    
                           
                            fullfilename=self.save_speed_image(image2,ave_speed,veh,frame[1])
                            self.write_speed_record(veh, fullfilename,ave_speed, cal_obj_mm, cal_obj_px,frame[1])
                        if cfg.gui_window_on:
                            image2=self._show_screen_speed(veh,image2)
                        if cfg.spaceTimerHrs > 0:
                            self.lastSpaceCheck = sfu.freeDiskSpaceCheck(self.lastSpaceCheck)
                        # Manage a maximum number of files
                        # and delete oldest if required.
                        if cfg.image_max_files > 0:
                            sfu.deleteOldFiles(cfg.image_max_files,self.speed_path,cfg.image_prefix)
                        # Save most recent files
                        # to a recent folder if required
                        if cfg.imageRecentMax > 0 and not cfg.calibrate:
                            sfu.saveRecent(cfg.imageRecentMax,cfg.imageRecentDir,fullfilename,cfg.image_prefix)

                        
                    else:
                        overlayLogger.info("Tracking complete- Skipped photo, Speed %.1f %s"
                                    " max_speed_over=%i  %i px in %.3f sec"
                                    " C=%i A=%i sqpx",
                                    ave_speed, rc.speed_units,
                                    cfg.max_speed_over, tot_track_dist,
                                    tot_track_time, total_contours,
                                    veh.biggest_area)
                    # Optional Wait to avoid multiple recording of same object
                    overlayLogger.debug(horiz_line)

                    if cfg.track_timeout > 0:
                        self.skip_frames=int(cfg.track_timeout*vs.fps)
                        overlayLogger.debug("skipping %i frames for %0.2f Sec (to avoid tracking same vehicle)",
                                     self.skip_frames,cfg.track_timeout)
                    # Track Ended so Reset 
                    veh.active=False
                    
                else: #still counting
                    #cv2.imshow('added', image2)
                    overlayLogger.debug("Added- %i/%i xy(%i,%i) %3.1f %s"
                                        " D=%i/%i %i sqpx %s",
                                        track_count, cfg.track_counter,
                                        veh.cur_track_x, veh.cur_track_y,
                                        ave_speed, rc.speed_units,
                                        abs(veh.cur_track_x - self.vehicle_prev_pos_x),
                                        cfg.x_diff_max,
                                        veh.track_list[-1].track_h*veh.track_list[-1].track_w,
                                        veh.track_list[-1].direction)
                    self.vehicle_end_pos_x = veh.cur_track_x
            # Movement was not within range parameters
            else:
                if cfg.show_out_range:
                    # movements exceeds Max px movement
                    # allowed so ignore 
                    #cv2.imshow('Out of Range', image2)
                    
                    if abs(veh.cur_track_x - self.vehicle_prev_pos_x) >= cfg.x_diff_max:
                        overlayLogger.debug(" Excess movement - %i/%i xy(%i,%i) Max D=%i>=%ipx"
                                    " C=%i %ix%i=%i sqpx %s",
                                    track_count+1, cfg.track_counter,
                                    veh.cur_track_x, veh.cur_track_y,
                                    abs(veh.cur_track_x - self.vehicle_prev_pos_x),
                                    cfg.x_diff_max,
                                    total_contours,
                                    veh.track_w, veh.track_h, veh.biggest_area,
                                    veh.travel_direction)
                        # if track_count is over half way then do not start new track
                        if track_count > cfg.track_counter / 2:
                            pass
                        else:
                            self.first_event = True    # Too Far Away so restart Track
                    # Did not move much so ignore
                    # and wait for next valid movement.
                    else:
                        overlayLogger.debug(" Diff too small - %i/%i xy(%i,%i) Min D=%i<=%ipx"
                                    " C=%i %ix%i=%i sqpx %s",
                                    track_count, cfg.track_counter,
                                    veh.cur_track_x, veh.cur_track_y,
                                    abs(veh.cur_track_x - self.vehicle_end_pos_x),
                                    cfg.x_diff_min,
                                    total_contours,
                                    veh.track_w, veh.track_h, veh.biggest_area,
                                    veh.travel_direction)
                        # Restart Track if first event otherwise continue
                        if track_count == 0:
                            self.first_event = True
        return True

    def _show_screen_speed(self,veh  :Vehicle, image):
        image1=image.copy()
        image_text = ("Last Speed %.1f %s " % (veh.FinalSpeed,rc.speed_units))
        text_x = 100
        #text_x = int((image_width / 2) - (len(image_text) * image_font_size / 3))
        if text_x < 2:
            text_x = 2
        jeff=cv2.putText(image1,image_text,(text_x, 300),self.font,cfg.image_font_scale,cfg.image_font_color,cfg.image_font_thickness)
        cv2.imshow("Speed",jeff)
        return jeff
    
    def write_speed_record(self,veh,filename, ave_speed,cal_obj_mm, cal_obj_px,timestamp):

        log_time = datetime.datetime.fromtimestamp(timestamp)
        #log_time = datetime.datetime.now()
        log_idx = ("%04d%02d%02d-%02d%02d%02d%d" %
                            (log_time.year,
                                log_time.month,
                                log_time.day,
                                log_time.hour,
                                log_time.minute,
                                log_time.second,
                                log_time.microsecond/100000))
        log_timestamp = ("%s%04d-%02d-%02d %02d:%02d:%02d%s" %
                                    (quote,
                                    log_time.year,
                                    log_time.month,
                                    log_time.day,
                                    log_time.hour,
                                    log_time.minute,
                                    log_time.second,
                                    quote))
        m_area = veh.track_w*veh.track_h
        if webcam:
            camera = "WebCam"
        else:
            camera = "PiCam"
        if cfg.overlayEnable:
            overlay_name = cfg.overlayName
        else:
            overlay_name = "Default"
        # create the speed data list ready for db insert
        speed_data = (log_idx,
                                log_timestamp,
                                camera,
                                round(ave_speed, 2), rc.speed_units, filename,
                                image_width, image_height, cfg.image_bigger,
                                veh.track_list[-1].direction, overlay_name,
                                veh.cur_track_x, veh.cur_track_y,
                                veh.track_w, veh.track_h, m_area,
                                self.x_left, self.x_right,
                                self.y_upper, self.y_lower,
                                cfg.max_speed_over,
                                cfg.MIN_AREA, cfg.track_counter,
                                cal_obj_px, cal_obj_mm, '', cfg.CAM_LOCATION)

        # Insert speed_data into sqlite3 database table
        # Note cam_location and status may not be in proper order unless speed table is recreated.
        if cfg.log_data_to_DB:
            sql_cmd = '''insert into {} values {}'''.format(cfg.DB_TABLE, speed_data)
            self.speed_db.db_add_record(sql_cmd)
            
        # Format and Save Data to CSV Log File
        if cfg.log_data_to_CSV:
            log_csv_time = ("%s%04d-%02d-%02d %02d:%02d:%02d%s"
                            % (quote,
                            log_time.year,
                            log_time.month,
                            log_time.day,
                            log_time.hour,
                            log_time.minute,
                            log_time.second,
                            quote))
            log_csv_text = ("%s,%.1f,%s%s%s,%.1f,%s%s%s,%i,%s%s%s,%s%s%s"
                            % (log_csv_time,
                            ave_speed,
                            quote,
                            rc.speed_units,
                            quote,
                            veh.StdDev,
                            quote,
                            filename,
                            quote,
                            veh.track_w * veh.track_h,
                            quote,
                            veh.track_list[-1].direction,
                            quote,
                            quote,
                            cfg.CAM_LOCATION,
                            quote))
            self.save_to_csv(log_csv_text)
        
    def save_speed_image(self,image2,ave_speed, veh,frame_timestamp):
        """ Resize and process previous image before saving to disk"""
        prev_image = image2
        # Create a calibration image file name
        # There are no subdirectories to deal with
        if cfg.calibrate:
            #log_time = datetime.datetime.now()
            fullfilename,filename = self._set_image_file_name(self.speed_path, "calib-",frame_timestamp)
            prev_image = self.take_calibration_image(ave_speed,
                                                fullfilename,
                                                prev_image)
        else:
            # Check if subdirectories configured
            # and create new subdirectory if required
            self.speed_path = sfu.subDirChecks(cfg.imageSubDirMaxHours,
                                    cfg.imageSubDirMaxFiles,
                                    image_path, cfg.image_prefix)

            # Record log_time for use later in csv and sqlite
            #log_time = datetime.datetime.now()
            # Create image file name
            if cfg.image_filename_speed:
                # add ave_speed value to filename after prefix
                speed_prefix = (cfg.image_prefix + str(int(round(ave_speed))) + '-')
                fullfilename,filename = self._set_image_file_name(self.speed_path, speed_prefix,frame_timestamp)
            else:
                # create image file name path
                fullfilename,filename = self._set_image_file_name(self.speed_path, cfg.image_prefix,frame_timestamp)

        # Add motion rectangle to image if required
        if cfg.image_show_motion_area:
            prev_image = self.speed_image_add_lines(prev_image, colours.cvRed)
            # show centre of motion if required
            if SHOW_CIRCLE:
                cv2.circle(prev_image,
                        (veh.cur_track_x + self.x_left, veh.cur_track_y + y_upper),
                        CIRCLE_SIZE,
                        colours.cvGreen, LINE_THICKNESS)
            if SHOW_RECTANGLE:
                cv2.rectangle(prev_image,
                            (int(veh.cur_track_x + self.x_left),
                            int(veh.cur_track_y + y_upper)),
                            (int(veh.cur_track_x + self.x_left + veh.track_w),
                            int(veh.cur_track_y + y_upper + veh.track_h)),
                            colours.cvGreen, LINE_THICKNESS)
        big_image = cv2.resize(prev_image,
                            (image_width,
                                image_height))
        if image_sign_on:
            image_sign_view_time = time.time()
            image_sign_bg = np.zeros((image_sign_resize[0], image_sign_resize[1], 4))
            image_sign_view = cv2.resize(image_sign_bg, (image_sign_resize))
            image_sign_text = str(int(round(ave_speed, 0)))
            cv2.putText(image_sign_view,
                        image_sign_text,
                        image_sign_text_xy,
                        self.font,
                        image_sign_font_scale,
                        image_sign_font_color,
                        image_sign_font_thickness)
        # Write text on image before saving
        # if required.
        if cfg.image_text_on:
            ts = datetime.datetime.fromtimestamp(frame_timestamp)
            tag = ts.strftime("%Y/%m/%d, %H:%M:%S")
            image_text = ("SPEED %.1f %s - %s"
                        % (ave_speed,
                            rc.speed_units,
                            tag))# was filename
            text_x = int((image_width / 2) -
                        (len(image_text) *
                        cfg.image_font_size / 3))
            if text_x < 2:
                text_x = 2
            cv2.putText(big_image,
                        image_text,
                        (text_x, self.text_y),
                        self.font,
                        cfg.image_font_scale,
                        cfg.image_font_color,
                        cfg.image_font_thickness)
        overlayLogger.info(" Saved %s", fullfilename)
        # Save resized image. If jpg format, user can customize image quality 1-100 (higher is better)
        # and/or enble/disable optimization per config.py settings.
        # otherwise if png, bmp, gif, etc normal image write will occur
        if cfg.image_format.lower() == ".jpg" or cfg.image_format.lower() == ".jpeg":
            cv2.imwrite(fullfilename, big_image, [int(cv2.IMWRITE_JPEG_QUALITY), cfg.image_jpeg_quality,
                                            int(cv2.IMWRITE_JPEG_OPTIMIZE), cfg.image_jpeg_optimize])
        else:
            cv2.imwrite(fullfilename, big_image)
        
        return fullfilename
    
    def _set_image_file_name(self,path, prefix,frame_timestamp):
        """ build image file names by number sequence or date/time Added tenth of second"""
        rightNow = datetime.datetime.fromtimestamp(frame_timestamp)
        filename = ("%s%04d%02d%02d_%02d%02d%02d%d.jpg" %
                    (prefix, rightNow.year, rightNow.month, rightNow.day,
                   rightNow.hour, rightNow.minute, rightNow.second, rightNow.microsecond/100000))
        qualified_pathname=os.path.join(path,filename)
        return qualified_pathname,filename
    
     
    def filter_mask(self,mask):
		# I want some pretty drastic closing
		#kernel_open = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
		#kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8))
		#kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
		#kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (20, 20))
		#kernel_dilate = cv2.getStructuringElement(cv2.MORPH_CROSS, (10, 5)) 
		#kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
		
		# Remove noise
        opening = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel_open,iterations=1)
		# Close holes within contours
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, self.kernel_close)
        #_, thresholded = cv2.threshold(closing, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
		# Merge adjacent blobs
        dilation = cv2.dilate(closing, self.kernel_dilate, iterations=3)
		# more iterations is more susceptible to noise but gives better shape
        #dilation = cv2.medianBlur(thresholded, 3)
		#fgmask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel1)
		#fgmask=cv2.erode(fgmask,self.kernel1,iterations=2)
		#dilation=cv2.dilate(fgmask, self.kernel1, iterations=4)
        return dilation

    def speed_get_contours(self,image, grayimage1):
        """
        Read Camera image and crop and process
        with opencv to detect motion contours.
        Added timeout in case camera has a problem.
        """
        image_ok = False
        start_time = time.time()
        timeout = 60 # seconds to wait if camera communications is lost.
                    # Note to self.  Look at adding setting to config.py
        while not image_ok:
            # crop image to motion tracking area only
            try:
                image_crop = image[self.y_upper:self.y_lower, self.x_left:self.x_right]
                image_ok = True
            except (ValueError, TypeError):#probably camera has disconnected
                overlayLogger.error("image Stream Image is Not Complete. Cannot Crop. Retrying...")
                if time.time() - start_time > timeout:
                    overlayLogger.error("%i second timeout exceeded.  Partial or No images received.", timeout)
                    overlayLogger.error("Possible camera or communication problem.  Please Investigate.")
                    sys.exit(1)
                else:
                    image_ok = False

        # Convert to gray scale, which is easier
        grayimage2 = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
        # Get differences between the two greyed images
        global differenceimage
        differenceimage = cv2.absdiff(grayimage1, grayimage2)
        # you can play around with different filtering etc, so all sorts of commented out stuff here
        #clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        #differenceimage=clahe.apply(differenceimage)
        #cv2.imshow('Diff', differenceimage)
        #differenceimage = self.filter_mask(differenceimage)
        # Find Canny edges
        edged = cv2.Canny(differenceimage, 100, 200)
        
        #edged=cv2.equalizeHist(edged)
        #edged = self.filter_mask(edged)
        
        #  Blur difference image to enhance motion vectors
        #differenceimage = cv2.blur(edged, (BLUR_SIZE, BLUR_SIZE))
        # Get threshold of blurred difference image
        # based on THRESHOLD_SENSITIVITY variable
        #retval, thresholdimage = cv2.threshold(differenceimage,
        #                                    THRESHOLD_SENSITIVITY,
        #                                    255, cv2.THRESH_BINARY)
        #thresholdimage = cv2.adaptiveThreshold(edged,
        # use THRESH_BINARY_INV to use a black background, stops picking up border as contour
        edged = cv2.adaptiveThreshold(edged,
                                              255,
                                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY_INV,11,2)
        #cv2.imshow('edged', edged)
        try:
            # opencv 2 syntax default
            contours, hierarchy = cv2.findContours(edged,
            #contours, hierarchy = cv2.findContours(thresholdimage,
                                                cv2.RETR_EXTERNAL,
                                                cv2.CHAIN_APPROX_SIMPLE)
        except ValueError:
            # opencv 3 syntax
            thresholdimage, contours, hierarchy = cv2.findContours(edged,
                                                                cv2.RETR_EXTERNAL,
                                                                cv2.CHAIN_APPROX_SIMPLE)
        #cv2.imshow('threshold', thresholdimage)
        # Update grayimage1 to grayimage2 ready for next image2
        grayimage1 = grayimage2
        cv2.drawContours(image_crop, contours, contourIdx=-1, color=(0, 255, 0), thickness=3)
        image_view = cv2.resize(image_crop, (int(image_width/2), int(image_height/2)))
        #cv2.imshow(self.contourwin, image_view)
        #cv2.imshow('contour', grayimage1)
    
        return grayimage1, contours
    
    def save_to_csv(self,data_to_append):
        """ Store date to a comma separated value file """
        data_file_path = os.path.join(baseDir, DB_DIR, cfg.overlayName+".csv")
        if not os.path.exists(data_file_path):
            open(data_file_path, 'w').close()
            f = open(data_file_path, 'ab')
            #TODO if needed, the header needs formatting and aligning with the csv data rows.
            # header_text = ('"YYYY-MM-DD HH:MM:SS","Speed","Unit",Variance,
            #                  "    Speed Photo Path            ",
            #                  "X","Y","W","H","Area","Direction"' + "\n")
            # f.write( header_text )
            f.close()
            overlayLogger.info("Created new data csv file %s", data_file_path)
        filecontents = data_to_append + "\n"
        f = open(data_file_path, 'a+')
        f.write(filecontents)
        f.close()
        overlayLogger.info("CSV - added speed data to %s", data_file_path)
        return

#--------------------------------------------------------------------------------------------------
class FoVDrawer(object):
    """Class for storing and retrieving the field of view mask"""
    def __init__(self,window_name):
        self.ref_rects=[]
        self.overlay_path=os.path.join(OVERLAYS_DIR,cfg.overlayName+'_settings.json')
        
    def load_mask(self):
        """Load saved field of view mask"""	
        if os.path.exists(self.overlay_path):
            with open(self.overlay_path, mode='r+',encoding='utf-8') as f:
                try:
                    mask_data = json.load(f)
                except Exception as e:
                    return None
                rect = mask_data['view_rect']
                overlayLogger.info('Loaded field of view from file')
                return rect
                                
                
    def save_mask(self,rect):
        """Write field of view mask to file for later use/loading """
        self.ref_rects=rect
        #road_name = sys.argv[1]
        save_rect=copy.deepcopy(rect)
        if os.path.exists(self.overlay_path):
            with open(self.overlay_path, mode='r+',encoding='utf-8') as f:
                try:
                    mask_data = json.load(f)
                    mask_data['view_rect'] = save_rect
                except Exception as e:
                    overlayLogger.error('Mask load error',e)
                    mask_data={'view_rect': save_rect}# restore the default
                   
                f.seek(0)
                json.dump(mask_data, f, indent=4)
                f.truncate()
                overlayLogger.info('Saved field of view mask to settings.json')
        else:
            mask_data={'view_rect': save_rect}
            with open(self.overlay_path, mode='w+',encoding='utf-8') as f:
                json.dump(mask_data, f, indent=4)
                f.truncate()
        
                  
 
    
   
#------------------------------------------------------------------------------------------
if __name__ == '__main__':
    rc=SpeedCam()
    readFromFile=cfg.src_is_file # gets the source images from a previously recorded file
    saveToFile=cfg.calibrate # saves a video of the camera to a video file
    x_left=cfg.x_left
    x_right=cfg.x_right
    y_lower=cfg.y_lower
    y_upper=cfg.y_upper
    #rd=RectangleDrawer()
    #pc=PolyCrop(rc.road)
    sfu=speed_file_utils.SpeedFileUtils()
    WebCamTryMax=3
    try:
        WebcamTries = 0
        while True:
            # Start Web Cam stream (Note USB webcam must be plugged in)
            if webcam:
                WebcamTries += 1
                overlayLogger.info("Initializing USB Web Camera Try .. %i",
                             WebcamTries)
                # Start video stream on a processor Thread for faster speed
                if readFromFile:
                    vs = WebcamVideoStream(CAM_SRC= cfg.source_file_name,isFile=readFromFile,isLoop=cfg.file_loop)#.start()
                else:
                    vs = WebcamVideoStream(saveStream=saveToFile,
                                           CAM_SRC = cfg.WEBCAM_SRC,
                                           CAM_WIDTH = cfg.WEBCAM_WIDTH,
                                           CAM_HEIGHT = cfg.WEBCAM_HEIGHT)
                    
                if vs.grabbed:
                    vs.start()
                else:
                    WebcamTries=WebCamTryMax+1
                if WebcamTries > WebCamTryMax:
                    overlayLogger.error("USB Web Cam Not Connecting to WEBCAM_SRC %i",
                                  cfg.WEBCAM_SRC)
                    overlayLogger.error("Check Camera is Plugged In and Working")
                    overlayLogger.error("on Specified SRC")
                    overlayLogger.error("and Not Used(busy) by Another Process.")
                    overlayLogger.error("%s %s Exiting Due to Error",
                                  progName, progVer)
                    vs.stop()
                    sys.exit(1)
                time.sleep(4.0)  # Allow WebCam to initialize
                overlayLogger.info("FPS %2f",vs.fps)
            else:
                overlayLogger.info("Initializing Pi Camera ....")
                # Start a pi-camera video stream thread
                vs = PiVideoStream().start()
                vs.camera.rotation = cfg.CAMERA_ROTATION
                vs.camera.hflip = cfg.CAMERA_HFLIP
                vs.camera.vflip = cfg.CAMERA_VFLIP
                time.sleep(2.0)  # Allow PiCamera to initialize

            # Get actual image size from stream.
            # Necessary for IP camera
            test_img = vs.read()
            if test_img is None:
                vs.stop()
                raise ValueError( 'No frame found')
            img_height, img_width, _ = test_img[0].shape
            # Set width of trigger point image to save
            image_width = int(img_width * cfg.image_bigger)
            # Set height of trigger point image to save
            image_height = int(img_height * cfg.image_bigger)
            #rd.load_cropped(test_img[0])
            #pc.load_cropped_polys(test_img)
            
            x_scale = 8.0
            y_scale = 4.0
            # reduce motion area for larger stream sizes
            if img_width > 1000:
                x_scale = 3.0
                y_scale = 3.0

            # If motion box crop settings not found in config.ini then
            # Auto adjust the crop image to suit the real image size.
            # For details See comments in config.py Motion Events settings section
            try:
                x_left
            except NameError:
                x_left = int(img_width / x_scale)

            try:
                x_right
            except NameError:
                x_right = int(img_width - x_left)

            try:
                y_upper
            except NameError:
                y_upper = int(img_height / y_scale)

            try:
                y_lower
            except NameError:
                y_lower = int(img_height - y_upper)

            # setup buffer area to ensure contour is mostly contained in crop area
            #x_buf = int((x_right - x_left) / cfg.x_buf_adjust)

            init_settings()  # Show variable settings
            rect=(x_left,x_right,y_upper,y_lower)
            speedCam=SpeedTrack(readFromFile,rect,image_path)
           
    except KeyboardInterrupt:
        vs.stop()
        print("")
        appLogger.info("User Pressed Keyboard ctrl-c")
        appLogger.info("%s %s Exiting Program", progName, progVer)
        sys.exit()
    except SystemExit as e:
        if e.code==1:
            vs.stop()
            print("")
            appLogger.error(e)
        else:
            os.exit()
            appLogger.critical("%s %s Unknown error", progName, progVer)