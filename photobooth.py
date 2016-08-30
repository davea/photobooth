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

from camera import Camera, CameraError, CameraNotConnectedError
from printer import Printer

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s - %(message)s', level=logging.DEBUG)
logging.getLogger("PIL").setLevel(logging.CRITICAL) # We don't care about PIL
log = logging.getLogger("photobooth.main")


TEST_MODE = bool(os.getenv("TEST_MODE", False))

BURST_COUNT = 1
PRINT_PHOTOS = bool(os.getenv("PRINT_PHOTOS", False))
OVERLAY_ALPHA = 128

# global PiCamera instance
pi_camera = None
pi_camera_overlays = {}
# global Touchscreen instance
touchscreen = None


def take_dslr_photo():
    log.debug("Starting countdown...")
    for i in range(3, 0, -1):
        show_overlay("countdown{}".format(i))
        log.debug("{}!".format(i))
        time.sleep(1)
    log.debug("Taking photo with gphoto2...")
    show_overlay("cheese")
    try:
        photo_path = Camera().capture(count=BURST_COUNT, processing_callback=lambda: show_overlay("please_wait"))
    except CameraNotConnectedError:
        log.error("Camera isn't connected.")
        show_overlay("intro")
        return
    except CameraError:
        log.exception("Something went horribly wrong whilst trying to take a photo.")
        show_overlay("intro")
        return
    if photo_path is not None:
        show_photo(photo_path)
    else:
        show_overlay("intro", message="Oops, couldn't take photo! Try again!")

def update_battery_level():
    battery_level = Camera().battery_level
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

def show_overlay(name, remove_others=True, message=""):
    o = pi_camera_overlays[name]
    window = (0, 480-o['size'][1], o['size'][0], o['size'][1])
    overlay = pi_camera.add_overlay(o['bytes'], size=o['size'], alpha=OVERLAY_ALPHA, layer=4, window=window, fullscreen=False)
    if remove_others:
        remove_overlays(max_length=1)
    pi_camera.annotate_text = message
    if not message:
        update_battery_level()

def show_photo(path):
    _, image = load_image_for_overlay(path)
    display_image = image.resize((800, 532)).crop((0,26,800,506))
    print_image = image.resize((963, 640))
    remove_overlays()
    overlay = pi_camera.add_overlay(display_image.tobytes(), size=display_image.size, layer=3)
    if PRINT_PHOTOS:
        show_overlay("print_confirm", remove_others=False)
        if wait_for_print_confirmation():
            remove_overlays(max_length=1, reverse=True)
            show_overlay("printing", remove_others=False)
            send_image_to_printer(print_image)
            time.sleep(5)
    else:
        time.sleep(5)
    show_overlay("intro")

def wait_for_print_confirmation():
    time.sleep(10)
    return True

def send_image_to_printer(image):
    pass

def remove_overlays(max_length=0, reverse=False):
    while len(pi_camera.overlays) > max_length:
        pi_camera.remove_overlay(pi_camera.overlays[-1 if reverse else 0])

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
    except Exception:
        log.exception("some other exception caused a shutdown:")
    finally:
        teardown_picamera()

if __name__ == '__main__':
    main()
