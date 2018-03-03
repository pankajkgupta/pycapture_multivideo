#!/usr/bin/sudo python
################################################################################
# Python script to record multiple ptgrey cameras in parallel.
# The code sends specific triggers on the parallel port to signal the video recording status
# Reads config.ini for parameters for video recording
# Author(s)	: Pankaj Kumar Gupta
# email		: pankaj_kumar_gupta@brown.edu
################################################################################

import PyCapture2
import parallel
import time
from timeit import default_timer as clock
from datetime import datetime
from joblib import Parallel, delayed
import multiprocessing
from multiprocessing import Pool
import os
from ConfigParser import SafeConfigParser
from subprocess import call
import gc
import resource
import sys

def printBuildInfo():
	libVer = PyCapture2.getLibraryVersion()
	print "PyCapture2 library version: ", libVer[0], libVer[1], libVer[2], libVer[3]
	print

def printCameraInfo(cam):
	camInfo = cam.getCameraInfo()
	print "\n*** CAMERA INFORMATION ***\n"
	print "Serial number - ", camInfo.serialNumber
	print "Camera model - ", camInfo.modelName
	print "Camera vendor - ", camInfo.vendorName
	print "Sensor - ", camInfo.sensorInfo
	print "Resolution - ", camInfo.sensorResolution
	print "Firmware version - ", camInfo.firmwareVersion
	print "Firmware build time - ", camInfo.firmwareBuildTime
	print

def sendTrigger(code):
	global trigWidth
	re_ordered = ""
	bnry = "{0:08b}".format(code)[::-1]
	for pin in pin_order: re_ordered += bnry[pin]
	ordered_code	= int(re_ordered[::-1], 2)
	for tl in range(trigWidth):
		p.setData(ordered_code)


def saveVideo(iCam):
	global record
	global n_epoch
	# Select camera on ith index
	cam = PyCapture2.Camera()
	cam.connect(bus.getCameraFromIndex(iCam))

	# Print camera details
	printCameraInfo(cam)
	record = 1
	vid_idx = 1

	try:
		print "Starting capture..."
		cam.startCapture()
	except:
		record = 0

	print "Detecting frame rate from Camera"
	fRateProp = cam.getProperty(PyCapture2.PROPERTY_TYPE.FRAME_RATE)
	frameRate = fRateProp.absValue

	print "Using frame rate of {}".format(frameRate)

	if iCam == 0:
		sendTrigger(T_SESSION_START)

	time.sleep(0.1)

	t_start = datetime.now()

	while record:
		vidFileName = dataPath + os.sep + "cam" + str(iCam) + os.sep + "cam{:02}_{:05}.avi".format(iCam, vid_idx)
		logFileName = dataPath + os.sep + "cam" + str(iCam) + os.sep + "cam{:02}_{:05}.txt".format(iCam, vid_idx)
		avi = PyCapture2.AVIRecorder()
		with open(logFileName, 'w') as logFile:
			if iCam == 0:
				sendTrigger(T_VID_START)
				tr_vid_epoch = 1
			try:

				for i in range(1,vidLen+1):
					# print '\n=== first: ' + str(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000)
					if not record:
						break
						
					try:
						image = cam.retrieveBuffer()
						sttime = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
					except PyCapture2.Fc2error as fc2Err:
						print "Error retrieving buffer : ", fc2Err
						continue

					if (i == 1):
						# if fileFormat == "H264":
						# avi.H264Open(vidFileName, frameRate, image.getCols(), image.getRows(), 200000000)
						# avi.AVIOpen(vidFileName, frameRate)
						avi.MJPGOpen(vidFileName, frameRate, 100)

					if iCam == 0:
						if tr_vid_epoch == n_epoch:
							tr_vid_epoch = 1
						if i % T_INTERVAL == 0:
							# print "\n\nSend frame: " + str(i)
							sendTrigger(tr_vid_epoch)
							tr_vid_epoch += 1
							print "Trigger sent: Video : {}	Frame : {}	Time : {} ...".format(vid_idx,
																											   i,
																											   datetime.now() - t_start)
						else:
							sendTrigger(T_BG)

					avi.append(image)
					logFile.write(str(i) + '\t' + sttime + "\n")
					# print "Press ctrl + c to quit... Video : {}	Frame : {}	Time : {} ...".format(vid_idx, i, datetime.now()-t_start)

			except KeyboardInterrupt:
				record = 0
				# if iCam == 0:
				# 	sendTrigger(T_VID_END)
				# 	print "Stopping capture...11"

			print "Appended {} images to file: {}...".format(vidLen, vidFileName)
			# if iCam == 0:
			# 	sendTrigger(T_VID_END)
			# 	print "Stopping capture..."
			avi.close()
			logFile.close()
			del avi
			vid_idx += 1

	# print "Stopping capture..."
	print "Stopping capture..."
	cam.stopCapture()
	cam.disconnect()


configSec 	= 'DEFAULT'
config 		= SafeConfigParser()
config.read('config.ini')

vidLen 		= int(config.get(configSec, 'vidLen'))
dataPath 	= config.get(configSec, 'dataPath')
trigWidth		= int(config.get(configSec, 'trigWidth'))

T_SESSION_START = int(config.get(configSec, 'T_SESSION_START'))
T_VID_START = int(config.get(configSec, 'T_VID_START'))
T_INTERVAL  = int(config.get(configSec, 'T_INTERVAL'))
T_BG		= int(config.get(configSec, 'T_BG'))
n_epoch		= int(config.get(configSec, 'N_EPOCH'))
pin_order	= map(int, (config.get(configSec, 'PIN')).split(','))

if __name__ == "__main__":
	try:
		call(["modprobe", "ppdev"])
	except:
		print "Exception caught removing lp driver\n\n"

	# Try removing the printer driver that gets installed on each reboot of the machine
	try:
		call(["rmmod", "lp"])
	except:
		print "Exception caught removing lp driver\n\n"


	# Print PyCapture2 Library Information
	printBuildInfo()

	# PyCapture2.Config.grabMode = 1
	# PyCapture2.Config.highPerformanceRetrieveBuffer = 1
	# Ensure sufficient cameras are found
	bus = PyCapture2.BusManager()
	numCams = bus.getNumOfCameras()

	print "Number of cameras detected: ", numCams
	if not numCams:
		print "Insufficient number of cameras. Exiting..."
		exit()

	# Get the current time and initialize the project folder
	t = datetime.now()
	dataPath = dataPath + str(t.year) + format(t.month, '02d') + format(t.day, '02d') + \
			   format(t.hour, '02d') + format(t.minute, '02d') + format(t.second, '02d')
	if not os.path.exists(dataPath):
		print "Creating data directory: %s" % dataPath
		os.makedirs(dataPath)
		for cam in range(numCams):
			os.makedirs(dataPath + os.sep + "cam" + str(cam))

	# save the configuration used
	with open(dataPath + '/config.ini', 'w') as f:
		config.write(f)

	p = parallel.Parallel()

	num_cores = multiprocessing.cpu_count()
	print 'number of cpu cores: ' + str(num_cores)

	sendTrigger(0)

	t1 = clock()

	try:
		Parallel(n_jobs=numCams)(delayed(saveVideo)(i) for i in range(0, numCams))
	except KeyboardInterrupt:
		print "Stopping video recording."

	t2 = clock()

	sendTrigger(0)

	print 'time taken ' + str(t2 - t1)
