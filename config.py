# ---------------- User Configuration Settings for speed-cam.py ---------------------------------
#         Ver 1.00 speed-cam.py Variable Configuration Settings

#######################################
#  speed-cam.py Variable Settings retrieval
#  
#######################################
import os
import logging
import shutil
import sys
import defaults
import glob

#TODO: rationalise python variable styles per pep 8
progVer = "1.00"

# this version doesn't support (external) image sign, but kept for ref.
image_sign_on = False
image_sign_show_camera = False
image_sign_resize = (128, 720)
image_sign_text_xy = (100, 675)
image_sign_font_scale = 30.0
image_sign_font_thickness = 60
image_sign_font_color = (255, 255, 255)
image_sign_timeout = 5        # Keep the image sign for 5 seconds.

# constants
OVERLAYS_DIR="overlays"
# OpenCV Motion Settings
# ----------------------
# when both of these are False, only the actual contour will show
SHOW_CIRCLE = False           # True=circle in center of motion,
SHOW_RECTANGLE = False        #True= rectangle around motion

CIRCLE_SIZE = 5               # Default= 5 Diameter circle in px if SHOW_CIRCLE = True
LINE_THICKNESS = 1            # Default= 1 Size of lines for circle or Rectangle
FONT_SCALE = 0.5              # Default= 0.5 OpenCV window text font size scaling factor Default=.5 (lower is smaller)

# Sqlite3 Settings
# ----------------
DB_DIR   = "data"

# matplotlib graph image settings -not used in this ver
# -------------------------------
GRAPH_PATH = 'media/graphs'  # Directory path for storing graph images
GRAPH_ADD_DATE_TO_FILENAME = False  # True - Prefix graph image filenames with datetime default = False
GRAPH_RUN_TIMER_HOURS = 0.5   # Default= 0.5 Update Graphs every specified hours wait (Continuous).
# List of sql query Data for sql-make-graph-count-totals.py and sql-make-graph-speed-ave.py (with no parameters)
#                [[Group_By, Days_Prev, Speed_Over]]  where Group_By is 'hour', 'day' or 'month'
GRAPH_RUN_LIST = [
                  ['day', 28, 10],
                  ['hour', 28, 10],
                  ['hour', 7, 0],
                  ['hour', 2, 0]
                 ]

#======================================
#       webserver.py Settings
#======================================

# Web Server settings - not used in this ver
# -------------------
web_server_port = 8080        # Default= 8080 Web server access port eg http://192.168.1.100:8080
web_server_root = "media"     # Default= "media" webserver root path to webserver image/video sub-folders
web_page_title = "SPEED-CAMERA Media"  # web page title that browser show (not displayed on web page)
web_page_refresh_on = True    # False=Off (never)  Refresh True=On (per seconds below)
web_page_refresh_sec = "900"  # Default= "900" seconds to wait for web page refresh  seconds (15 minutes)
web_page_blank = False        # True Starts left image with a blank page until a right menu item is selected
                              # False displays second list[1] item since first may be in progress

# Left iFrame Image Settings
# --------------------------
web_image_height = "768"       # Default= "768" px height of images to display in iframe
web_iframe_width_usage = "70%" # Left Pane - Sets % of total screen width allowed for iframe. Rest for right list
web_iframe_width = "100%"      # Desired frame width to display images. can be eg percent "80%" or px "1280"
web_iframe_height = "100%"     # Desired frame height to display images. Scroll bars if image larger (percent or px)

# Right Side Files List
# ---------------------
web_max_list_entries = 0           # 0 = All or Specify Max right side file entries to show (must be > 1)
web_list_height = web_image_height # Right List - side menu height in px (link selection)
web_list_by_datetime = True        # True=datetime False=filename
web_list_sort_descending = True    # reverse sort order (filename or datetime per web_list_by_datetime setting



# ---------------------------------------------- End of Program Constants -----------------------------------------------------
class Config:
    """Class to hold user variables read from an ini file using python configparser rules,
    and application constants"""
   

    def __init__(self, baseDir,logger):
        self.baseDir=baseDir
        self.parser=None
        self.appLogger=logger
        self.load_settings()# load the basic settings 
        self.check_overlay()# check to see if there is an overlay ini
        self.retrieve_settings()#read the config ini overwritten by overlayini settings (if any)
        
        
        
    
    def load_settings(self):
        self.settingsFilePath = os.path.join(self.baseDir, "config.ini")
        if os.path.exists(self.settingsFilePath):
        # Read Configuration variables from config.ini file
            try:
                from configparser import ConfigParser
                self.parser=ConfigParser(inline_comment_prefixes="#",converters={'tuple':self.parse_int_tuple})
                self.parser.read(['config.ini'])
            except ImportError:
                print('WARN  : Import of ConfigParser failed')
            except FileNotFoundError:
                print("WARN  : Missing config.ini file - File Not Found %s" % self.settingsFilePath)
        else:
            print("WARN  : Missing config.ini file - File Not Found %s" % self.settingsFilePath)

    def get_base_path(self):
        # Get information about this script including name, launch path, etc.   
        # This allows script to be renamed or relocated to another directory
        mypath = os.path.abspath(__file__)  # Find the full path of this python script
        # get the path location only (excluding script name)
        self.baseDir = mypath[0:mypath.rfind("/")+1]
        self.baseFileName = mypath[mypath.rfind("/")+1:mypath.rfind(".")]
        self.progName = os.path.basename(__file__)
        
    def get_current_overlay(self,overlayName):
        overlayDir = os.path.join(self.baseDir, OVERLAYS_DIR)
        # Check if there is a .ini at the end of overlayName variable
        if overlayName.endswith('.ini'):
            overlayName = overlayName[:-4]    # Remove .ini extension
        overlayPath = os.path.join(overlayDir, overlayName + '.ini')

        self.appLogger.info("overlayEnabled - loading overlayName %s", overlayPath)
        if not os.path.isdir(overlayDir):
            self.appLogger.error("overlay Directory Not Found at %s", overlayDir)
            self.appLogger.warn("%s %s Exiting Due to Error", self.progName, progVer)
            sys.exit(1)
        elif not os.path.exists(overlayPath):
            self.appLogger.error("File Not Found overlayName %s", overlayPath)
            self.appLogger.info("Check Spelling of overlayName Value in %s", self.settingsFilePath)
            self.appLogger.info("------- Valid Names -------")
            validPlugin = glob.glob(overlayDir + "/*ini")
            validPlugin.sort()
            for entry in validPlugin:
                overlayFile = os.path.basename(entry)
                overlay = overlayFile.rsplit('.', 1)[0]
                if not ((overlay == "__init__") or (overlay == "current")):
                    logging.info("        %s", overlay)
            self.appLogger.info("------- End of List -------")
            self.appLogger.info("        Note: supply overlay name without extension.")
            self.appLogger.warn("%s %s Exiting Due to Error", self.progName, progVer)
            sys.exit(1)
        else:
            overlayCurrent = os.path.join(overlayDir, "current.ini")
            try:    # Copy image file to recent folder
                self.appLogger.info("Copy %s to %s", overlayPath, overlayCurrent)
                shutil.copy(overlayPath, overlayCurrent)
            except OSError as err:
                self.appLogger.error('Copy Failed from %s to %s - %s',
                            overlayPath, overlayCurrent, err)
                self.appLogger.info("Check permissions, disk space, Etc.")
                self.appLogger.warn("%s %s Exiting Due to Error", self.progName, progVer)
                sys.exit(1)
            self.appLogger.info("Imported Overlay %s", overlayPath)
            # add overlay directory to program PATH
            sys.path.insert(0, overlayDir)
            self.overlayPath=overlayPath
            return overlayCurrent, overlayDir

    def check_overlay(self):
        """Check to see if an overlay is specified in the config.ini"""
        Overlays=self.parser['Overlays']
        self.overlayEnable=Overlays.getboolean('overlayEnable')
        if self.overlayEnable:
            self.overlayName=Overlays.get('overlayName')
            a,b=self.get_current_overlay(self.overlayName)
            self.parser.read([a])
        else:
            self.overlayname='default'


    def retrieve_settings(self):
        """Get all the settings from the config and overlay files"""
        Source=self.parser['Source']
        self.src_is_file=Source.getboolean('file_src',False)
        self.source_file_name=Source.get('source_file_name')
        self.file_loop= Source.getboolean('file_loop', True)
        Calibration=self.parser['Calibration']
        self.calibrate=Calibration.getboolean('calibrate',False)
        self.cal_obj_mm_R2L=Calibration.getfloat('cal_obj_mm_R2L',4700.0)
        self.cal_obj_px_L2R = Calibration.getfloat('cal_obj_px_L2R', 80) 
        self.cal_obj_mm_L2R=Calibration.getfloat('cal_obj_mm_L2R',4700.0)
        self.cal_obj_px_R2L = Calibration.getfloat('cal_obj_px_R2L',100)
        self.hash_colour = [int(c) for c in (Calibration.get('hash_colour','255,0,0').split(','))]
        self.hash_colour.reverse() #opencv uses BGR
        self.motion_win_colour = [int(c) for c in (Calibration.get('motion_win_colour','0,0,255').split(','))]
        self.motion_win_colour.reverse()
        Gui=self.parser['GUI']
        self.gui_window_on = Gui.getboolean('gui_window', True)  # True= Turn On All desktop GUI openCV windows. False=Don't Show (req'd for SSH) .
        self.gui_show_camera = Gui.getboolean('gui_show_camera',True) # True=Show the camera on gui windows. False=Don't Show (useful for image_sign)
        self.show_thresh_on = Gui.getboolean('show_thresh_on',False) # Display desktop GUI openCV cropped threshold window. True=Show, False=Don't Show
        self.show_crop_on =  Gui.getboolean('show_crop_on', False)   # Same as show_thresh_on but in color. True=Show, False=Don't Show (Default)
        self.window_bigger=1.0
        #self.window_bigger=Gui.getfloat('window_bigger',1.0)
        Logging=self.parser['Logging']
        self.verbose=Logging.getboolean('verbose',False) # True= Display basic status information on console False= Off
        self.log_fps =Logging.getboolean('log_fps', False)    # True= Show average frame count every 1000 loops False= Off
        self.log_data_to_CSV = Logging.getboolean('log_data_to_csv', True) # True= Save log data as CSV comma separated values  False= Off
        self.log_data_to_DB = Logging.getboolean('log_data_to_db', False) # True= Save log data to SQL database
        self.loggingToFile = Logging.getboolean('loggingToFile', False)  # True= Send logging to file False= No Logging to File
        #self.logFilePath = Logging.get('logFilePath','speed-cam.log')  # Location of log file when loggingToFile=True
        self.maxLogSize= Logging.getint('maxLogSize',1E6)
        self.logBackups=Logging.getint('logBackups',0)
        Motion=self.parser['Motion']
        
        self.SPEED_MPH = Motion.getboolean('SPEED_MPH', True) # Set Speed Units   kph=False  mph=True
        self.track_counter = Motion.getint('track_counter', 10) # Default= 6 Number of Consecutive Motion Events to trigger speed photo. Adjust to suit.
                       # Suggest single core cpu=4-7 quad core=8-15 but adjust to smooth erratic readings due to contour jumps
        self.MIN_AREA = Motion.getint('MIN_AREA', 1000)  # Default= 200 Exclude all contours less than or equal to this sq-px Area
        self.show_out_range = Motion.getboolean('show_out_of_range', False)  # Default= True Show Out of Range Events per x_diff settings below False= Off
        self.x_diff_max = Motion.getint('x_diff_max', 40 ) # Default= 20 Exclude if max px away >= last motion event x position
        self.x_diff_min = Motion.getint('x_diff_min', 1)  # Default= 1 Exclude if min px away <= last event x position
        self.y_diff_max = Motion.getint('y_diff_max', 10)
        #self.x_buf_adjust = Motion.getint('x_buf_adjust',10)  # Default= 10 Divides motion Rect x for L&R Buffer Space to Ensure contours are in
        self.track_timeout = Motion.getfloat('track_timeout', 1) # Default= 0.5 Optional seconds to wait after track End (Avoids dual tracking)
        #self.event_timeout = Motion.getfloat('event_timeout', 0.3) # Default= 0.3 seconds to wait for next motion event before starting new track
        self.max_speed_over = Motion.getfloat('max_speed_over', 8)     # Exclude track if Speed less than or equal to value specified 0=All
                       # Can be useful to exclude pedestrians and/or bikes, Etc or track only fast objects
        self.max_speed_count= Motion.getfloat('max_speed_count', 65)  # dont't count anything over this speed, probably wrong
        self.x_left =  Motion.getint('x_left',220)  # uncomment and change values to override auto calculate
        self.x_right = Motion.getint('x_right', 430)# uncomment and change values to override auto calculate

        self.y_upper = Motion.getint('y_upper', 20)  # uncomment and change values to override auto calculate
        self.y_lower = Motion.getint('y_lower', 160) # uncomment and change values to override auto calculate
        Webcam=self.parser['WebCam']
        self.CAM_LOCATION = Webcam.get('CAM_LOCATION','Location1')  # Specify an address, physical location Etc for camera
        self.WEBCAM = Webcam.getboolean('WEBCAM', True)  # Default= False False=PiCamera True= USB Webcam or RTSP,IP Camera

        self.WEBCAM_SRC = Webcam.get('WEBCAM_SRC',"") # Default= 0   USB camera device connection number
                       # or RTSP cam string eg "rtsp://192.168.1.101/RtspTranslator.12/camera"
        self.WEBCAM_WIDTH = Webcam.getint('WEBCAM_WIDTH',640) # Default= 320 USB Webcam Image width ignored for RTSP cam
        self.WEBCAM_HEIGHT = Webcam.getint('WEBCAM_HEIGHT', 480)    # Default= 240 USB Webcam Image height ignored for RTSP cam
        self.WEBCAM_HFLIP = Webcam.getboolean('WEBCAM_HFLIP', False) # Default= False USB Webcam flip image horizontally
        self.WEBCAM_VFLIP = Webcam.getboolean('WEBCAM_VFLIP', False) # Default= False USB Webcam flip image vertically
        PiCamera= self.parser['PiCamera']

        self.CAMERA_WIDTH = PiCamera.getint('CAMERA_WIDTH', 320)     # Image stream width for opencv motion scanning Default=320
        self.CAMERA_HEIGHT = PiCamera.getint('CAMERA_HEIGHT',240)    # Image stream height for opencv motion scanning  Default=240
        self.CAMERA_FRAMERATE = PiCamera.getfloat('CAMERA_FRAMERATE', 22)  # Default= 20 Frame rate for video stream V2 picam can be higher
        self.CAMERA_ROTATION = PiCamera.getint('CAMERA_ROTATION',0)  # Rotate camera image valid values are 0, 90, 180, 270
        self.CAMERA_VFLIP = PiCamera.getboolean('CAMERA_VFLIP', True)    # Flip the camera image vertically if required
        self.CAMERA_HFLIP = PiCamera.getboolean('CAMERA_HFLIP', True)    # Flip the camera image horizontally if required
        Image= self.parser['Image']
        self.image_path = Image.get('image_path', 'media/image')   # folder name to store images
        self.image_prefix = Image.get('image_prefix', "speed_")     # image name prefix
        self.image_format = Image.get('image_format', ".jpg")  # Default = ".jpg"  image Formats .jpg .jpeg .png .gif .bmp
        self.image_jpeg_quality = 95 # Set the quality of the jpeg. Default = 95 https://docs.opencv.org/3.4/d8/d6a/group__imgcodecs__flags.html#ga292d81be8d76901bff7988d18d2b42ac
        self.image_jpeg_optimize = True    # Optimize the image. Default = False https://docs.opencv.org/3.4/d8/d6a/group__imgcodecs__flags.html#ga292d81be8d76901bff7988d18d2b42ac
        self.image_show_motion_area = Image.getboolean('image_show_motion_area', True) # True= Display motion detection rectangle area on saved images
        self.image_filename_speed = Image.getboolean('image_filename_speed', False)  # True= Prefix filename with speed value
        self.image_text_on = Image.getboolean('image_text_on', True) # True= Show Text on speed images   False= No Text on images
        self.image_text_bottom = Image.getboolean('image_bottom_text',True)      # True= Show image text at bottom otherwise at top
        self.image_font_size = Image.getint('image_font_size', 12)  # Default= 12 Font text height in px for text on images
        self.image_font_scale = Image.getfloat('image_font_scale', 0.5)  # Default= 0.5 Font scale factor that is multiplied by the font-specific base size.
        self.image_font_thickness = Image.getint('image_font_thickness',2)  # Default= 2  Font text thickness in px for text on images
        self.image_font_color = Image.gettuple('image_font_color', (255, 255, 255))  # Default= (255, 255, 255) White
        self.image_bigger = Image.getfloat('image_bigger', 3.0)    # Default= 3.0 min=0.1 Resize saved speed image by specified multiplier value
        self.image_max_files = Image.getint('image_max_files', 0) # 0=off or specify MaxFiles to maintain then oldest are deleted  Default=0 (off)
        self.imageRecentMax = Image.getint('imageRecentMax',0)  # 0=off  Maintain specified number of most recent files in motionRecentDir
        self.imageRecentDir = Image.get('imageRecentDir',"media/recent")  # Default= "media/recent"  save recent files directory path

        Sqlite3= self.parser['Sqlite3']
        self.DB_DIR   = Sqlite3.get('DB_DIR', "data")
        self.DB_NAME  = Sqlite3.get('DB_NAME', "speed_cam.db")
        self.DB_TABLE = Sqlite3.get('DB_TABLE', "speed")
        FileManager=self.parser['Files']
        self.spaceTimerHrs = FileManager.getfloat('spaceTimerHrs',0) # Default= 0  0=off or specify hours frequency to perform free disk space check
        self.spaceFreeMB = FileManager.getfloat('spaceFreeMB',500)   # Default= 500  Target Free space in MB Required.
        self.spaceMediaDir = FileManager.get('spaceMediaDir','media/images')  # Default= 'media/images'  Starting point for directory walk
        self.spaceFileExt  = FileManager.get ('spaceFileExt','jpg')  # Default= 'jpg' File extension to Delete Oldest Files
        self.imageSubDirMaxFiles = FileManager.getint('imageSubDirMax',2000)    # 0=off or specify MaxFiles - Creates New dated sub-folder if MaxFiles exceeded
        self.imageSubDirMaxHours = FileManager.getfloat('imageSubDirMaxHours',0)  # 0=off or specify MaxHours - Creates New dated sub-folder if MaxHours exceeded


        for key, val in defaults.default_settings.items():
            try:
                val=self.parser['Settings'][key]
                exec(key +'=val')
            except KeyError:
                print('WARN  : config.ini Variable Not Found. Setting ' + key + ' = ' + str(val))
                exec(key + '=val')

    def parse_int_tuple(self,input):
      return tuple(int(k.strip()) for k in input[1:-1].split(','))

    