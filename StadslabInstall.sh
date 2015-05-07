#!/bin/bash          
echo Starting install of Stadslab Printcloud!
sudo usermod -a -G tty pi
sudo usermod -a -G dialout pi
sudo rm -r ~/.octoprint1
sudo mkdir ~/.octoprint1
sudo rm -r ~/.octoprint2
sudo mkdir ~/.octoprint2
sudo rm -r ~/.octoprint3
sudo mkdir ~/.octoprint3
sudo rm -r ~/.octoprint4
sudo mkdir ~/.octoprint4
sudo cp config/.octoprint ./octoprint1
sudo cp config/.octoprint ./octoprint2
sudo cp config/.octoprint ./octoprint3
sudo cp config/.octoprint ./octoprint4


