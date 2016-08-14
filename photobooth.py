#!/usr/bin/env python3
import os
import time
import tempfile
import random

from picamera import PiCamera, Color
from ft5406 import Touchscreen
import gphoto2 as gp

TEST_MODE = bool(os.getenv("TEST_MODE", False))

MESSAGES = {
    "cheese": "SAY CHEESE!",
    "touch_screen": "Touch the screen to take a photo!",
    "saving": "Lovely!",
}

BURST_COUNT = 1

# global variables (ick) for gphoto2
gp_context = None
gp_camera = None
# global PiCamera instance
pi_camera = None
# global Touchscreen instance
touchscreen = None

def setup_gphoto():
    global gp_context, gp_camera
    gp_context = gp.gp_context_new()
    gp_camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(gp_camera, gp_context))

def teardown_gphoto():
    gp.check_result(gp.gp_camera_exit(gp_camera, gp_context))

def take_dslr_photo(count=BURST_COUNT):
    print("Starting countdown...")
    for i in range(3, 0, -1):
        pi_camera.annotate_text = "{}!".format(i)
        print("{}!".format(i))
        time.sleep(1)
    for i in range(count):
        print("Taking photo with gphoto2...")
        pi_camera.annotate_text = MESSAGES['cheese']
        file_path = gp.check_result(gp.gp_camera_capture(
            gp_camera, gp.GP_CAPTURE_IMAGE, gp_context))
        print("Took photo")
        pi_camera.annotate_text = MESSAGES['saving']
        f, target = tempfile.mkstemp(".jpg")
        camera_file = gp.check_result(gp.gp_camera_file_get(
                gp_camera, file_path.folder, file_path.name,
                gp.GP_FILE_TYPE_NORMAL, gp_context))
        print("Got file")
        gp.check_result(gp.gp_file_save(camera_file, target))
        print("Saved to {}".format(target))
    pi_camera.annotate_text = MESSAGES['touch_screen']

def setup_touchscreen():
    global touchscreen
    touchscreen = Touchscreen()
    for touch in touchscreen.touches:
        if touch.slot == 0:
            touch.on_press = lambda e, t: take_dslr_photo()

def setup_picamera():
    global pi_camera
    pi_camera = PiCamera()
    pi_camera.start_preview()
    pi_camera.vflip = True
    pi_camera.annotate_background = Color('black')
    pi_camera.annotate_text = MESSAGES['touch_screen']

def teardown_picamera():
    pi_camera.stop_preview()
    pi_camera.close()

def main():
    setup_picamera()
    setup_gphoto()
    setup_touchscreen()
    print("Running in test mode" if TEST_MODE else "Running in interactive mode")
    try:
        while True:
            if TEST_MODE:
                for i in range(random.randint(1, 10)):
                    take_dslr_photo()
                    sleep = random.randint(0, 3)
                    print("Sleeping for {} seconds...".format(sleep))
                    time.sleep(sleep)
                sleep = random.randint(30, 60*15)
                print("Sleeping for {} seconds...".format(sleep))
                time.sleep(sleep)
            else:
                for touch in touchscreen.poll():
                    touch.handle_events()
    except KeyboardInterrupt:
        print("Caught Ctrl-C, shutting down...")
    finally:
        teardown_picamera()
        teardown_gphoto()

if __name__ == '__main__':
    main()
