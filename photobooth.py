#!/usr/bin/env python3
import os
import time
import logging
import tempfile
import random
from glob import glob

from picamera import PiCamera, Color
from ft5406 import Touchscreen
from PIL import Image

from camera import Camera

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s - %(message)s', level=logging.DEBUG)
logging.getLogger("PIL").setLevel(logging.CRITICAL) # We don't care about PIL
log = logging.getLogger("photobooth.main")


TEST_MODE = bool(os.getenv("TEST_MODE", False))

BURST_COUNT = 1
OVERLAY_ALPHA = 128

# global variables (ick) for gphoto2
gp_camera = None
# global PiCamera instance
pi_camera = None
pi_camera_overlays = {}
# global Touchscreen instance
touchscreen = None


def take_dslr_photo():
    global gp_camera
    if gp_camera is None:
        log.debug("Creating Camera object")
        gp_camera = Camera()
    log.debug("Starting countdown...")
    for i in range(3, 0, -1):
        show_overlay("countdown{}".format(i))
        log.debug("{}!".format(i))
        time.sleep(1)
    log.debug("Taking photo with gphoto2...")
    show_overlay("cheese")
    photo_path = gp_camera.capture(count=BURST_COUNT, processing_callback=lambda: show_overlay("please_wait"))
    show_photo(photo_path)

def update_battery_level():
    battery_level = gp_camera.battery_level if gp_camera is not None else None
    if battery_level is not None and battery_level <= 25:
        pi_camera.annotate_text = "Camera battery low! {}%".format(battery_level)
    else:
        pi_camera.annotate_text = ""

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
    show_overlay('intro')

def setup_overlays():
    for filename in glob("overlays/*.png"):
        name = os.path.basename(filename).rsplit(".png", 1)[0]
        size, image = load_image_for_overlay(filename)
        pi_camera_overlays[name] = {
            'bytes': image.tobytes(),
            'size': size,
        }
        log.debug("Loaded '{}' overlay".format(name))

def load_image_for_overlay(path):
    # Load the arbitrarily sized image
    img = Image.open(path)
    # Create an image padded to the required size with
    # mode 'RGB'
    pad = Image.new('RGB', (
        ((img.size[0] + 31) // 32) * 32,
        ((img.size[1] + 15) // 16) * 16,
        ))
    # Paste the original image into the padded one
    pad.paste(img, (0, 0))
    return img.size, pad

def show_overlay(name):
    o = pi_camera_overlays[name]
    window = (0, 480-o['size'][1], o['size'][0], o['size'][1])
    overlay = pi_camera.add_overlay(o['bytes'], size=o['size'], alpha=OVERLAY_ALPHA, layer=4, window=window, fullscreen=False)
    while len(pi_camera.overlays) > 1:
        pi_camera.remove_overlay(pi_camera.overlays[0])
    update_battery_level()

def show_photo(path):
    _, image = load_image_for_overlay(path)
    image = image.resize((800, 532)).crop((0,26,800,506))
    while pi_camera.overlays:
        pi_camera.remove_overlay(pi_camera.overlays[0])
    overlay = pi_camera.add_overlay(image.tobytes(), size=image.size, layer=3)

    # wait for a few seconds or until the screen is tapped
    time.sleep(5)
    show_overlay("intro")

def teardown_picamera():
    pi_camera.stop_preview()
    pi_camera.close()

def main():
    setup_picamera()
    setup_touchscreen()
    log.debug("Running in test mode" if TEST_MODE else "Running in interactive mode")
    try:
        while True:
            if TEST_MODE:
                for i in range(random.randint(1, 10)):
                    take_dslr_photo()
                    sleep = random.randint(0, 3)
                    log.debug("Sleeping for {} seconds...".format(sleep))
                    time.sleep(sleep)
                # sleep = random.randint(30, 60*15)
                sleep = random.randint(10, 20)
                log.debug("Sleeping for {} seconds...".format(sleep))
                time.sleep(sleep)
            else:
                for touch in touchscreen.poll():
                    touch.handle_events()
    except KeyboardInterrupt:
        log.info("Caught Ctrl-C, shutting down...")
    finally:
        teardown_picamera()

if __name__ == '__main__':
    main()
