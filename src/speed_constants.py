class Speed_Errors(object):
		ERROR_SUCCESS=0
		ERROR_OUT_OF_RANGE=1
		ERROR_AREA_TOO_SMALL=2
		ERROR_Y_SHIFT_TOO_LARGE=4
		ERROR_X_SHIFT_TOO_SMALL=8
		ERROR_X_SHIFT_TOO_LARGE=16
		ERROR_X_SHIFT_NEGATIVE=32
		ERROR_TIMEOUT=64
        
        
class Speed_Colours(object):
	cvRed = (0, 0, 255)
	cvWhite = (255, 255, 255)
	cvBlack = (0, 0, 0)
	cvBlue = (255, 0, 0)
	cvGreen = (0, 255, 0)
	FINAL_LINE_COLOR = (0, 0, 0)
	WORKING_LINE_COLOR = (127, 127, 127)

class Speed_Constants(object):
    X_DIFF_MAX = 100
    X_DIFF_MIN = 1
    Y_DIFF_MAX = 10
		