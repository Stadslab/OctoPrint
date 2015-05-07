#!/bin/bash          
echo Starting Stadslab Printcloud!
OCTOPRINT_HOME=/home/pi/OctoPrint

$OCTOPRINT_HOME/run --daemon start

$OCTOPRINT_HOME/run --daemon start --port 5001 --pid /tmp/octoprint2 --basedir ~/.octoprint1