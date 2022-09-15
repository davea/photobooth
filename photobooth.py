#!/usr/bin/env python3
import os
import time
from datetime import datetime
import queue
import random
import logging
import tempfile
from glob import glob
from configparser import ConfigParser

from picamera2 import Picamera2, Preview
from libcamera import Transform
from ft5406 import Touchscreen
from PIL import Image, ImageOps
import numpy as np

from camera import Camera, CameraError, CameraNotConnectedError
from printer import Printer

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s - %(thread)d - %(message)s",
    level=logging.DEBUG,
)
logging.getLogger("PIL").setLevel(logging.CRITICAL)  # We don't care about PIL
log = logging.getLogger("photobooth.main")

config = ConfigParser()
config.read("config.ini")

# global PiCamera instance
pi_camera = None
pi_camera_overlays = {}
# global Touchscreen instance
touchscreen = None
touchscreen_queue = queue.Queue()
# global Camera instance
dslr_camera = None
# global Printer instance
printer = None


def take_photo():
    log.debug("Starting countdown...")
    for i in range(3, 0, -1):
        show_overlay("countdown{}".format(i))
        log.debug("{}!".format(i))
        time.sleep(0.1)
    log.debug("Taking photo...")
    show_overlay("cheese")
    photo_path = None
    if dslr_camera:
        try:
            photo_path = dslr_camera.capture(
                count=config["camera"].getint("burst_count"),
                processing_callback=lambda: show_overlay("please_wait"),
            )
        except CameraNotConnectedError:
            log.error("Camera isn't connected.")
            show_overlay("intro")
            return
        except CameraError:
            log.exception(
                "Something went horribly wrong whilst trying to take a photo."
            )
            show_overlay("intro")
            return
    else:
        # fall back to capturing from picamera
        photo_path = f"{config['camera']['output_dir']}{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.jpg"
        pi_camera.capture_file(photo_path)
    if photo_path is not None:
        show_photo(photo_path)
    else:
        show_overlay("intro", message="Oops, couldn't take photo! Try again!")
    clear_touches()


def update_battery_level():
    battery_level = dslr_camera.battery_level
    if battery_level is not None and battery_level <= config["camera"].getint(
        "battery_warning"
    ):
        pi_camera.annotate_text = "Camera battery low! {}%".format(battery_level)
    else:
        pi_camera.annotate_text = ""


def setup_touchscreen():
    global touchscreen
    try:
        touchscreen = Touchscreen(device=config["touchscreen"]["device"])
    except RuntimeError:
        log.error("Couldn't connect to touchscreen, is device connected?")
        return
    for touch in (t for t in touchscreen.touches if t.slot == 0):
        touch.on_press = lambda e, t: screen_pressed(t.x, t.y)
    touchscreen.run()


def teardown_touchscreen():
    try:
        touchscreen.stop()
    except Exception:
        log.exception("Couldn't teardown touchscreen:")


def screen_pressed(x, y):
    if not x and not y:
        log.debug(f"Ignoring touch at {x},{y}")
    log.debug(f"Screen pressed at {x},{y}, enqueuing")
    touchscreen_queue.put((x, y))


def setup_picamera():
    global pi_camera
    setup_overlays()
    pi_camera = Picamera2()
    pi_camera.configure(pi_camera.create_preview_configuration())
    pi_camera.start_preview(
        Preview.DRM,
        width=config["preview"].getint("width"),
        height=config["preview"].getint("height"),
        transform=Transform(
            hflip=config["preview"].getint("hflip"),
            vflip=config["preview"].getint("vflip"),
        ),
    )
    pi_camera.start()
    show_overlay("intro")


def setup_overlays():
    for filename in glob("overlays/*.png"):
        name = os.path.basename(filename).rsplit(".png", 1)[0]
        size, image = load_image_for_overlay(filename)
        pi_camera_overlays[name] = {
            "img": image,
            "size": size,
        }
        log.debug("Loaded '{}' overlay".format(name))


def load_image_for_overlay(path):
    h = config["overlay"].getint("height")
    w = config["overlay"].getint("width")
    pad = Image.new("RGBA", (w, h))
    # Load the arbitrarily sized image
    img = Image.open(path)
    # Paste the original image into the padded one
    coord = (0, h - img.size[1] - config["overlay"].getint("pad_y"))
    pad.paste(img, coord)
    if config["overlay"].getint("hflip"):
        pad = ImageOps.mirror(pad)
    if config["overlay"].getint("vflip"):
        pad = ImageOps.flip(pad)
    return img.size, pad


def show_overlay(name, remove_others=True, message=""):
    log.debug(f"show_overlay {name}")

    o = pi_camera_overlays[name]

    pi_camera.set_overlay(np.array(o["img"]))
    return
    o = pi_camera_overlays[name]
    window = (
        0,
        config["general"].getint("screen_height") - o["size"][1],
        o["size"][0],
        o["size"][1],
    )
    overlay = pi_camera.add_overlay(
        o["bytes"],
        size=o["size"],
        alpha=config["general"].getint("overlay_alpha"),
        layer=4,
        window=window,
        fullscreen=False,
    )
    if remove_others:
        remove_overlays(max_length=1)
    pi_camera.annotate_text = message
    if not message:
        update_battery_level()


def show_photo(path):
    log.debug(f"show_photo {path}")
    return
    _, image = load_image_for_overlay(path)
    display_image = image.resize((config["general"].getint("screen_width"), 532)).crop(
        (0, 26, 800, 506)
    )
    remove_overlays()
    overlay = pi_camera.add_overlay(
        display_image.tobytes(), size=display_image.size, layer=3
    )
    if printer:
        show_overlay("print_confirm", remove_others=False)
        if (
            config["printer"].getboolean("print_everything")
            or wait_for_print_confirmation()
        ):
            remove_overlays(max_length=1, reverse=True)
            show_overlay("printing", remove_others=False)
            Printer(config=config).print(image)
    else:
        time.sleep(config["camera"].getint("review_timeout"))
    remove_overlays()
    time.sleep(0.5)
    show_overlay("intro")


def wait_for_print_confirmation():
    clear_touches()
    x, y = touchscreen_queue.get()
    # If the touch was on the bottom right quadrant of the screen, assume the
    # user wants to print the displayed image.
    return x > (config["general"].getint("screen_width") / 2) and y > (
        config["general"].getint("screen_height") / 2
    )


def remove_overlays(max_length=0, reverse=False):
    log.debug("remove_overlays")
    return
    while len(pi_camera.overlays) > max_length:
        pi_camera.remove_overlay(pi_camera.overlays[-1 if reverse else 0])


def teardown_picamera():
    try:
        pi_camera.stop_preview()
        pi_camera.close()
    except Exception:
        log.exception("Couldn't teardown picamera:")


def main_loop():
    # We're on the main screen waiting for the screen to be tapped...
    while True:
        # time.sleep(1)
        touchscreen_queue.get()
        log.debug("dequeued a touch")
        take_photo()


def clear_touches():
    # The touchscreen might receive touches when we're in the middle of
    # something else (e.g. showing the countdown, previewing print, sending to
    # printer), and if we don't clear them they'll cause unexpected events
    # when we return to the main loop.
    # This method discards any queued touches so we can be sure the next touch
    # is one we actually care about.
    while True:
        try:
            touchscreen_queue.get(False)
            log.debug("ignored a touch")
        except queue.Empty:
            log.debug("touchscreen_queue empty")
            break


def setup_dslr():
    global dslr_camera
    dslr_camera = Camera(config)


def setup_printer():
    global printer
    if config["printer"].getboolean("enabled"):
        printer = Printer(config)


def main():
    # setup_dslr()
    setup_printer()
    setup_picamera()
    setup_touchscreen()
    try:
        main_loop()
    except KeyboardInterrupt:
        log.info("Caught Ctrl-C, shutting down...")
    except Exception:
        log.exception("some other exception caused a shutdown:")
    finally:
        teardown_picamera()
        teardown_touchscreen()


if __name__ == "__main__":
    main()
