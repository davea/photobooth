# Raspberry Pi photobooth

A little project to use a Raspberry Pi as a photobooth at weddings etc. The code is not really in any fit state for reuse, sorry, so proceed with caution!

## Requirements

 - Raspberry Pi
 - Raspberry Pi camera (for capturing the live preview)
 - Raspberry Pi touchscreen (viewfinder/UI for taking photos)
 - [gPhoto-compatible](http://gphoto.org/doc/remote/) DSLR (for taking decent quality photos)

## Installation

 1. Install required raspbian packages (`sudo aptitude install gphoto2 libjpeg-dev build-essential python3.4-dev python3.4 python3-pip virtualenvwrapper`, probably others)
 1. Create a Python 3.4 virtualenv: `mkvirtualenv -p $(which python3) photobooth`
 1. Upgrade pip: `pip install --upgrade pip`
 1. Install python packages: `pip install -r requirements.txt`
 1. Run the script: `python photobooth.py`
