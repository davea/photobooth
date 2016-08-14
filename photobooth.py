#!/usr/bin/env python3
import os
import time
import tempfile
import random
from glob import glob

from picamera import PiCamera, Color
from ft5406 import Touchscreen
from PIL import Image
import gphoto2 as gp

TEST_MODE = bool(os.getenv("TEST_MODE", False))

BURST_COUNT = 1
OVERLAY_ALPHA = 128

# global variables (ick) for gphoto2
gp_context = None
gp_camera = None
# global PiCamera instance
pi_camera = None
pi_camera_overlays = {}
# global Touchscreen instance
touchscreen = None

def setup_gphoto():
    global gp_context, gp_camera
    if gp_context is not None or gp_camera is not None:
        teardown_gphoto()
    print("Setting up gphoto connection")
    gp_context = gp.gp_context_new()
    gp_camera = gp.check_result(gp.gp_camera_new())
    gp.check_result(gp.gp_camera_init(gp_camera, gp_context))

def teardown_gphoto():
    global gp_context, gp_camera
    print("Closing gphoto connection")
    gp.check_result(gp.gp_camera_exit(gp_camera, gp_context))
    gp_context, gp_camera = None, None

def take_dslr_photo(count=BURST_COUNT):
    setup_gphoto()
    print("Starting countdown...")
    for i in range(3, 0, -1):
        set_camera_overlay("countdown{}".format(i))
        print("{}!".format(i))
        time.sleep(1)
    for i in range(count):
        print("Taking photo with gphoto2...")
        set_camera_overlay("cheese")
        file_path = gp.check_result(gp.gp_camera_capture(
            gp_camera, gp.GP_CAPTURE_IMAGE, gp_context))
        print("Took photo")
        f, target = tempfile.mkstemp(".jpg")
        camera_file = gp.check_result(gp.gp_camera_file_get(
                gp_camera, file_path.folder, file_path.name,
                gp.GP_FILE_TYPE_NORMAL, gp_context))
        print("Got file")
        gp.check_result(gp.gp_file_save(camera_file, target))
        print("Saved to {}".format(target))
    set_camera_overlay("intro")
    teardown_gphoto()

def setup_touchscreen():
    global touchscreen
    touchscreen = Touchscreen()
    for touch in touchscreen.touches:
        if touch.slot == 0:
            touch.on_press = lambda e, t: take_dslr_photo()

def setup_picamera():
    global pi_camera
    pi_camera = PiCamera()
    pi_camera.vflip = False
    pi_camera.hflip = True
    pi_camera.start_preview()
    setup_overlays()
    set_camera_overlay('intro')

def setup_overlays():
    for filename in glob("overlays/*.png"):
        name = os.path.basename(filename).rsplit(".png", 1)[0]
        # Load the arbitrarily sized image
        img = Image.open(filename)
        # Create an image padded to the required size with
        # mode 'RGB'
        print("loaded image")
        pad = Image.new('RGB', (
            ((img.size[0] + 31) // 32) * 32,
            ((img.size[1] + 15) // 16) * 16,
            ))
        print("created new image")
        # Paste the original image into the padded one
        pad.paste(img, (0, 0))
        print("pasted image")
        pi_camera_overlays[name] = {
            'bytes': pad.tobytes(),
            'size': img.size,
        }
        print("all done")

def set_camera_overlay(name):
    o = pi_camera_overlays[name]
    window = (0, 480-o['size'][1], o['size'][0], o['size'][1])
    overlay = pi_camera.add_overlay(o['bytes'], size=o['size'], alpha=OVERLAY_ALPHA, layer=3, window=window, fullscreen=False)
    while len(pi_camera.overlays) > 1:
        pi_camera.remove_overlay(pi_camera.overlays[0])

def teardown_picamera():
    pi_camera.stop_preview()
    pi_camera.close()

def main():
    setup_picamera()
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

if __name__ == '__main__':
    main()
