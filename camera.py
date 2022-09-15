import os
import time
import tempfile
from logging import getLogger
from datetime import datetime

import gphoto2 as gp

log = getLogger("photobooth.camera")


class Camera:
    _camera = None
    _context = None
    _output_dir = None
    _config = None
    _capture_failure_timeout = 0.1  # How long to wait between capture failures

    battery_level = None

    def __init__(self, config):
        self._output_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "captures")
        )
        self._config = config
        self._set_gphoto_config_values()

    def __del__(self):
        self._teardown()

    def _set_gphoto_config_values(self):
        self._setup()
        for name, value in self._config.items("gphoto"):
            log.debug("Setting gphoto option {} = {}".format(name, value))
            self._set_config(name, value)
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
        for _ in range(self._config["camera"].getint("max_retries")):
            try:
                file_path = gp.check_result(
                    gp.gp_camera_capture(
                        self._camera, gp.GP_CAPTURE_IMAGE, self._context
                    )
                )
                break
            except gp.GPhoto2Error as e:
                log.exception("Exception when taking picture! Trying again.")
                time.sleep(self._capture_failure_timeout)
        else:
            log.error(
                "Couldn't take a photo after {} attempts, giving up!".format(
                    self._config["camera"].getint("max_retries")
                )
            )
            return None
        log.info("Took photo")
        if callable(processing_callback):
            processing_callback()
        prefix = datetime.now().strftime("%Y-%m-%d-%H%M%S-")
        _, target = tempfile.mkstemp(prefix=prefix, suffix=".jpg", dir=self._output_dir)
        camera_file = gp.check_result(
            gp.gp_camera_file_get(
                self._camera,
                file_path.folder,
                file_path.name,
                gp.GP_FILE_TYPE_NORMAL,
                self._context,
            )
        )
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

    def _set_config(self, name, value):
        coercions = {"burstnumber": float}
        config = self._camera.get_config(self._context)
        widget = config.get_child_by_name(name)
        widget.set_value(coercions.get(name, str)(value))
        self._camera.set_config(config, self._context)


class CameraError(Exception):
    pass


class CameraNotConnectedError(CameraError):
    pass


if __name__ == "__main__":
    import logging

    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s - %(thread)d - %(message)s",
        level=logging.DEBUG,
    )
    from configparser import ConfigParser

    config = ConfigParser()
    config.read("config.ini")
    c = Camera(config)
    c._setup()
    print(c._get_config("iso"))
