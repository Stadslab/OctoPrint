from __future__ import absolute_import
# coding=utf-8
__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


import time
import os
import re
import threading
import math

from octoprint.settings import settings

class VirtualPrinter():
	def __init__(self):
		self.readList = ['start\n', 'Marlin: Virtual Marlin!\n', '\x80\n', 'SD card ok\n'] # no sd card as default startup scenario
		self.currentExtruder = 0
		self.temp = [0.0] * settings().getInt(["devel", "virtualPrinter", "numExtruders"])
		self.targetTemp = [0.0] * settings().getInt(["devel", "virtualPrinter", "numExtruders"])
		self.lastTempAt = time.time()
		self.bedTemp = 1.0
		self.bedTargetTemp = 1.0
		self.speeds = settings().get(["devel", "virtualPrinter", "movementSpeed"])

		self._relative = True
		self._lastX = None
		self._lastY = None
		self._lastZ = None
		self._lastE = None

		self._unitModifier = 1

		self._virtualSd = settings().getBaseFolder("virtualSd")
		self._sdCardReady = True
		self._sdPrinter = None
		self._sdPrintingSemaphore = threading.Event()
		self._selectedSdFile = None
		self._selectedSdFileSize = None
		self._selectedSdFilePos = None
		self._writingToSd = False
		self._newSdFilePos = None
		self._heatupThread = None

		self.currentLine = 0
		self.lastN = 0

		waitThread = threading.Thread(target=self._sendWaitAfterTimeout)
		waitThread.start()

	def write(self, data):
		if self.readList is None:
			return

		data = data.strip()

		# strip checksum
		if "*" in data:
			data = data[:data.rfind("*")]
			self.currentLine += 1
		elif settings().getBoolean(["devel", "virtualPrinter", "forceChecksum"]):
			self.readList.append("Error: Missing checksum")
			return

		# track N = N + 1
		if data.startswith("N") and "M110" in data:
			linenumber = int(re.search("N([0-9]+)", data).group(1))
			self.lastN = linenumber
			self.currentLine = linenumber
			self.readList.append("ok")
			return
		elif data.startswith("N"):
			linenumber = int(re.search("N([0-9]+)", data).group(1))
			expected = self.lastN + 1
			if linenumber != expected:
				self.readList.append("Error: expected line %d got %d" % (expected, linenumber))
				self.readList.append("Resend:%d" % expected)
				self.readList.append("ok")
				return
			elif self.currentLine == 100:
				# simulate a resend at line 100 of the last 5 lines
				self.lastN = 94
				self.readList.append("Error: Line Number is not Last Line Number\n")
				self.readList.append("rs %d\n" % (self.currentLine - 5))
				self.readList.append("ok")
				return
			else:
				self.lastN = linenumber
			data = data.split(None, 1)[1].strip()

		data += "\n"

		# shortcut for writing to SD
		if self._writingToSd and not self._selectedSdFile is None and not "M29" in data:
			with open(self._selectedSdFile, "a") as f:
				f.write(data)
			self._sendOk()
			return

		#print "Send: %s" % (data.rstrip())
		if 'M104' in data or 'M109' in data:
			if not self._parseHotendCommand(data):
				return
		if 'M140' in data or 'M190' in data:
			if not self._parseBedCommand(data):
				return

		if 'M105' in data:
			# send simulated temperature data
			if settings().getInt(["devel", "virtualPrinter", "numExtruders"]) > 1:
				allTemps = []
				for i in range(len(self.temp)):
					allTemps.append((i, self.temp[i], self.targetTemp[i]))
				allTempsString = " ".join(map(lambda x: "T%d:%.2f /%.2f" % x, allTemps))
				if settings().getBoolean(["devel", "virtualPrinted", "includeCurrentToolInTemps"]):
					self.readList.append("ok T:%.2f /%.2f B:%.2f /%.2f %s @:64\n" % (self.temp[self.currentExtruder], self.targetTemp[self.currentExtruder] + 1, self.bedTemp, self.bedTargetTemp, allTempsString))
				else:
					self.readList.append("ok %s B:%.2f /%.2f @:64\n" % (allTempsString, self.bedTemp, self.bedTargetTemp))
			else:
				self.readList.append("ok T:%.2f /%.2f B:%.2f /%.2f @:64\n" % (self.temp[0], self.targetTemp[0], self.bedTemp, self.bedTargetTemp))
		elif 'M20' in data:
			if self._sdCardReady:
				self._listSd()
		elif 'M21' in data:
			self._sdCardReady = True
			self.readList.append("SD card ok")
		elif 'M22' in data:
			self._sdCardReady = False
		elif 'M23' in data:
			if self._sdCardReady:
				filename = data.split(None, 1)[1].strip()
				self._selectSdFile(filename)
		elif 'M24' in data:
			if self._sdCardReady:
				self._startSdPrint()
		elif 'M25' in data:
			if self._sdCardReady:
				self._pauseSdPrint()
		elif 'M26' in data:
			if self._sdCardReady:
				pos = int(re.search("S([0-9]+)", data).group(1))
				self._setSdPos(pos)
		elif 'M27' in data:
			if self._sdCardReady:
				self._reportSdStatus()
		elif 'M28' in data:
			if self._sdCardReady:
				filename = data.split(None, 1)[1].strip()
				self._writeSdFile(filename)
		elif 'M29' in data:
			if self._sdCardReady:
				self._finishSdFile()
		elif 'M30' in data:
			if self._sdCardReady:
				filename = data.split(None, 1)[1].strip()
				self._deleteSdFile(filename)
		elif "M114" in data:
			# send dummy position report
			self.readList.append("ok C: X:10.00 Y:3.20 Z:5.20 E:1.24")
		elif "M117" in data:
			# we'll just use this to echo a message, to allow playing around with pause triggers
			self.readList.append("ok %s" % re.search("M117\s+(.*)", data).group(1))
		elif "M999" in data:
			# mirror Marlin behaviour
			self.readList.append("Resend: 1")
		elif data.startswith("T"):
			self.currentExtruder = int(re.search("T(\d+)", data).group(1))
			self._sendOk()
			self.readList.append("Active Extruder: %d" % self.currentExtruder)
		elif "G20" in data:
			self._unitModifier = 1.0 / 2.54
			if self._lastX is not None:
				self._lastX *= 2.54
			if self._lastY is not None:
				self._lastY *= 2.54
			if self._lastZ is not None:
				self._lastZ *= 2.54
			if self._lastE is not None:
				self._lastE *= 2.54
			self._sendOk()
		elif "G21" in data:
			self._unitModifier = 1.0
			if self._lastX is not None:
				self._lastX /= 2.54
			if self._lastY is not None:
				self._lastY /= 2.54
			if self._lastZ is not None:
				self._lastZ /= 2.54
			if self._lastE is not None:
				self._lastE /= 2.54
			self._sendOk()
		elif "G90" in data:
			self._relative = False
			self._sendOk()
		elif "G91" in data:
			self._relative = True
			self._sendOk()
		elif "G92" in data:
			self._setPosition(data)
			self._sendOk()
		elif "G0" in data or "G1" in data:
			# simulate movement duration -- no acceleration, only linear movement duration based on max speed
			self._performMove(data)
			self._sendOk()
		elif len(data.strip()) > 0:
			self._sendOk()

	def _listSd(self):
		self.readList.append("Begin file list")
		for osFile in os.listdir(self._virtualSd):
			self.readList.append(osFile.upper())
		self.readList.append("End file list")
		self._sendOk()

	def _selectSdFile(self, filename):
		file = os.path.join(self._virtualSd, filename).lower()
		if not os.path.exists(file) or not os.path.isfile(file):
			self.readList.append("open failed, File: %s." % filename)
		else:
			self._selectedSdFile = file
			self._selectedSdFileSize = os.stat(file).st_size
			self.readList.append("File opened: %s  Size: %d" % (filename, self._selectedSdFileSize))
			self.readList.append("File selected")

	def _startSdPrint(self):
		if self._selectedSdFile is not None:
			if self._sdPrinter is None:
				self._sdPrinter = threading.Thread(target=self._sdPrintingWorker)
				self._sdPrinter.start()
		self._sdPrintingSemaphore.set()
		self._sendOk()

	def _pauseSdPrint(self):
		self._sdPrintingSemaphore.clear()
		self._sendOk()

	def _setSdPos(self, pos):
		self._newSdFilePos = pos

	def _reportSdStatus(self):
		if self._sdPrinter is not None and self._sdPrintingSemaphore.is_set:
			self.readList.append("SD printing byte %d/%d" % (self._selectedSdFilePos, self._selectedSdFileSize))
		else:
			self.readList.append("Not SD printing")

	def _parseHotendCommand(self, line):
		tool = 0
		toolMatch = re.search('T([0-9]+)', line)
		if toolMatch:
			try:
				tool = int(toolMatch.group(1))
			except:
				pass

		if tool >= settings().getInt(["devel", "virtualPrinter", "numExtruders"]):
			return

		try:
			self.targetTemp[tool] = float(re.search('S([0-9]+)', line).group(1))
		except:
			pass

		if "M109" in line:
			self._heatupThread = threading.Thread(target=self._waitForHeatup, args=["tool%d" % tool])
			self._heatupThread.start()
			return False
		return True

	def _parseBedCommand(self, line):
		try:
			self.bedTargetTemp = float(re.search('S([0-9]+)', line).group(1))
		except:
			pass

		if "M190" in line:
			self._heatupThread = threading.Thread(target=self._waitForHeatup, args=["bed"])
			self._heatupThread.start()
			return False
		return True

	def _performMove(self, line):
		matchX = re.search("X([0-9.]+)", line)
		matchY = re.search("Y([0-9.]+)", line)
		matchZ = re.search("Z([0-9.]+)", line)
		matchE = re.search("E([0-9.]+)", line)

		duration = 0
		if matchX is not None:
			try:
				x = float(matchX.group(1))
				if self._relative or self._lastX is None:
					duration = max(duration, x * self._unitModifier / float(self.speeds["x"]) * 60.0)
				else:
					duration = max(duration, (x - self._lastX) * self._unitModifier / float(self.speeds["x"]) * 60.0)
				self._lastX = x
			except:
				pass
		if matchY is not None:
			try:
				y = float(matchY.group(1))
				if self._relative or self._lastY is None:
					duration = max(duration, y * self._unitModifier / float(self.speeds["y"]) * 60.0)
				else:
					duration = max(duration, (y - self._lastY) * self._unitModifier / float(self.speeds["y"]) * 60.0)
				self._lastY = y
			except:
				pass
		if matchZ is not None:
			try:
				z = float(matchZ.group(1))
				if self._relative or self._lastZ is None:
					duration = max(duration, z * self._unitModifier / float(self.speeds["z"]) * 60.0)
				else:
					duration = max(duration, (z - self._lastZ) * self._unitModifier / float(self.speeds["z"]) * 60.0)
				self._lastZ = z
			except:
				pass
		if matchE is not None:
			try:
				e = float(matchE.group(1))
				if self._relative or self._lastE is None:
					duration = max(duration, e * self._unitModifier / float(self.speeds["e"]) * 60.0)
				else:
					duration = max(duration, (e - self._lastE) * self._unitModifier / float(self.speeds["e"]) * 60.0)
				self._lastE = e
			except:
				pass

		if duration:
			time.sleep(duration)

	def _setPosition(self, line):
		matchX = re.search("X([0-9.]+)", line)
		matchY = re.search("Y([0-9.]+)", line)
		matchZ = re.search("Z([0-9.]+)", line)
		matchE = re.search("E([0-9.]+)", line)

		if matchX is None and matchY is None and matchZ is None and matchE is None:
			self._lastX = self._lastY = self._lastZ = self._lastE = 0
		else:
			if matchX is not None:
				try:
					self._lastX = float(matchX.group(1))
				except:
					pass
			if matchY is not None:
				try:
					self._lastY = float(matchY.group(1))
				except:
					pass
			if matchZ is not None:
				try:
					self._lastZ = float(matchZ.group(1))
				except:
					pass
			if matchE is not None:
				try:
					self._lastE = float(matchE.group(1))
				except:
					pass

	def _writeSdFile(self, filename):
		file = os.path.join(self._virtualSd, filename).lower()
		if os.path.exists(file):
			if os.path.isfile(file):
				os.remove(file)
			else:
				self.readList.append("error writing to file")

		self._writingToSd = True
		self._selectedSdFile = file
		self.readList.append("Writing to file: %s" % filename)
		self._sendOk()

	def _finishSdFile(self):
		self._writingToSd = False
		self._selectedSdFile = None
		self._sendOk()

	def _sdPrintingWorker(self):
		self._selectedSdFilePos = 0
		with open(self._selectedSdFile, "r") as f:
			for line in f:
				# reset position if requested by client
				if self._newSdFilePos is not None:
					f.seek(self._newSdFilePos)
					self._newSdFilePos = None

				# read current file position
				self._selectedSdFilePos = f.tell()

				# if we are paused, wait for unpausing
				self._sdPrintingSemaphore.wait()

				# set target temps
				if 'M104' in line or 'M109' in line:
					self._parseHotendCommand(line)
				if 'M140' in line or 'M190' in line:
					self._parseBedCommand(line)

				time.sleep(0.01)

		self._sdPrintingSemaphore.clear()
		self._selectedSdFilePos = 0
		self._sdPrinter = None
		self.readList.append("Done printing file")

	def _waitForHeatup(self, heater):
		delta = 0.5
		delay = 1
		if heater.startswith("tool"):
			toolNum = int(heater[len("tool"):])
			while self.temp[toolNum] < self.targetTemp[toolNum] - delta or self.temp[toolNum] > self.targetTemp[toolNum] + delta:
				self._simulateTemps()
				self.readList.append("T:%0.2f /%0.2f" % (self.temp[toolNum], self.targetTemp[toolNum]))
				time.sleep(delay)
		elif heater == "bed":
			while self.bedTemp < self.bedTargetTemp - delta or self.bedTemp > self.bedTargetTemp + delta:
				self._simulateTemps()
				self.readList.append("B:%0.2f /%0.2f" % (self.bedTemp, self.bedTargetTemp))
				time.sleep(delay)
		self.readList.append("ok")

	def _deleteSdFile(self, filename):
		f = os.path.join(self._virtualSd, filename)
		if os.path.exists(f) and os.path.isfile(f):
			os.remove(f)
		self._sendOk()

	def _simulateTemps(self):
		timeDiff = self.lastTempAt - time.time()
		self.lastTempAt = time.time()
		for i in range(len(self.temp)):
			if abs(self.temp[i] - self.targetTemp[i]) > 1:
				oldVal = self.temp[i]
				self.temp[i] += math.copysign(timeDiff * 10, self.targetTemp[i] - self.temp[i])
				if math.copysign(1, self.targetTemp[i] - oldVal) != math.copysign(1, self.targetTemp[i] - self.temp[i]):
					self.temp[i] = self.targetTemp[i]
				if self.temp[i] < 0:
					self.temp[i] = 0
		if abs(self.bedTemp - self.bedTargetTemp) > 1:
			oldVal = self.bedTemp
			self.bedTemp += math.copysign(timeDiff * 10, self.bedTargetTemp - self.bedTemp)
			if math.copysign(1, self.bedTargetTemp - oldVal) != math.copysign(1, self.bedTargetTemp - self.bedTemp):
				self.bedTemp = self.bedTargetTemp
			if self.bedTemp < 0:
				self.bedTemp = 0

	def readline(self):
		if self.readList is None:
			return ''
		n = 0

		self._simulateTemps()

		while len(self.readList) < 1:
			time.sleep(0.1)
			n += 1
			if n == 20:
				return ''
			if self.readList is None:
				return ''
		#time.sleep(0.001)
		return self.readList.pop(0)

	def close(self):
		self.readList = None

	def _sendOk(self):
		if settings().getBoolean(["devel", "virtualPrinter", "okWithLinenumber"]):
			self.readList.append("ok %d" % self.lastN)
		else:
			self.readList.append("ok")

	def _sendWaitAfterTimeout(self, timeout=5):
		time.sleep(timeout)
		if self.readList is not None:
			self.readList.append("wait")
