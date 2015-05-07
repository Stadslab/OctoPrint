#!/bin/bash          
echo Starting install of Stadslab Printcloud!
#need to add switching to devel branch
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
sudo cp .octoprint ./octoprint1
sudo cp .octoprint ./octoprint2
sudo cp .octoprint ./octoprint3
sudo cp .octoprint ./octoprint4


