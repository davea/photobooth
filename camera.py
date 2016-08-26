import os
import time
import tempfile
from logging import getLogger
from datetime import datetime

import gphoto2 as gp

log = getLogger("photobooth.camera")

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Camera(metaclass=Singleton):
    _camera = None
    _context = None
    _output_dir = None
    _max_retries = 5
    battery_level = None

    def __init__(self, max_retries=None):
        self._output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "captures"))
        if max_retries:
            self._max_retries = max_retries

    def __del__(self):
        self._teardown()

    def _setup(self):
        if self._camera is not None:
            log.debug("gphoto connection already set up")
            return
        log.debug("Setting up gphoto connection")
        self._context = gp.gp_context_new()
        self._camera = gp.check_result(gp.gp_camera_new())
        try:
            gp.check_result(gp.gp_camera_init(self._camera, self._context))
        except gp.GPhoto2Error as e:
            if e.code == gp.GP_ERROR_MODEL_NOT_FOUND:
                log.critical("Camera not connected!")
                raise CameraNotConnectedError()
            else:
                log.exception("An error occurred whilst trying to setup the camera.")
                raise CameraError()

    def _teardown(self):
        if self._camera is None:
            log.warning("Already closed gphoto connection")
            return
        log.debug("Closing gphoto connection")
        gp.check_result(gp.gp_camera_exit(self._camera, self._context))
        self._context, self._camera = None, None

    def capture(self, processing_callback=None, count=1):
        if self._camera is None:
            self._setup()
        for _ in range(self._max_retries):
            try:
                file_path = gp.check_result(gp.gp_camera_capture(
                    self._camera, gp.GP_CAPTURE_IMAGE, self._context))
                break
            except gp.GPhoto2Error as e:
                log.exception("Exception when taking picture! Trying again.")
                time.sleep(0.1)
        else:
            log.error("Couldn't take a photo after {} attempts, giving up!".format(self._max_retries))
            return None
        log.info("Took photo")
        if callable(processing_callback):
            processing_callback()
        prefix = datetime.now().strftime("%Y-%m-%d-%H%M%S-")
        _, target = tempfile.mkstemp(prefix=prefix, suffix=".jpg", dir=self._output_dir)
        camera_file = gp.check_result(gp.gp_camera_file_get(
                self._camera, file_path.folder, file_path.name,
                gp.GP_FILE_TYPE_NORMAL, self._context))
        log.debug("Got file")
        gp.check_result(gp.gp_file_save(camera_file, target))
        log.info("Saved to {}".format(target))
        self.update_battery_level()
        self._teardown()
        return target

    def update_battery_level(self):
        self.battery_level = int(self._get_config("batterylevel").rstrip("%"))

    def _get_config(self, name):
        config = self._camera.get_config(self._context)
        widget = config.get_child_by_name(name)
        return widget.get_value()

class CameraError(Exception): pass
class CameraNotConnectedError(CameraError): pass
