OctoPrint for Stadslab
=========
This fork is for usage within Stadslab Rotterdam, where we use multiple printers on one Raspberry Pi B+. We use OctoPrint so we can make some default slicing profiles, which is a huge contributor to user-errors. 

Right now the software sets up four separate webpages for a maximum of four printers (since the Pi has four USB-ports).
Those websites are available at {ip of your Pi}:5000 through 5003.


OctoPrint provides a responsive web interface for controlling a 3D printer (RepRap, Ultimaker, ...). It is Free Software
and released under the [GNU Affero General Public License V3](http://www.gnu.org/licenses/agpl.html).

Its website can be found at [octoprint.org](http://octoprint.org).

Contributing
------------

Please see the project's [Contribution Guidelines](https://github.com/foosel/OctoPrint/blob/master/CONTRIBUTING.md).

Installation
------------
This package is made for the Raspberry Pi. Your raspberry needs to be equipped with a (standard) version of Raspbian.
See the following steps to reproduce our environment:
### Basic setup

For the basic package you'll need Python 2.7 (should be installed by default) and pip. OctoPrint's dependencies will be installed by the `setup.py` script:  

    cd ~
    sudo apt-get update
    sudo apt-get install python-pip python-dev python-setuptools python-virtualenv git
    git clone https://github.com/Stadslab/OctoPrint.git
    cd OctoPrint
    virtualenv --system-site-packages venv
    ./venv/bin/python setup.py install
    
Now we will install the Stadslab-specific settings, by running 
    sudo ./StadslabInstall.sh


Dependencies
------------

OctoPrint depends on a couple of python modules to do its job. Those are automatically installed when installing
OctoPrint via `setup.py`:

    python setup.py install

You should also do this every time after pulling from the repository, since the dependencies might have changed.

OctoPrint currently only supports Python 2.7.


Usage
-----



Configuration
-------------

