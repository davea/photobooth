import os
import tempfile
from datetime import datetime

import gphoto2 as gp

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

    def __init__(self):
        self._output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "captures"))

    def __del__(self):
        self._teardown()

    def _setup(self):
        if self._context is not None and self._camera is not None:
            self._teardown()
        print("Setting up gphoto connection")
        self._context = gp.gp_context_new()
        self._camera = gp.check_result(gp.gp_camera_new())
        gp.check_result(gp.gp_camera_init(self._camera, self._context))

    def _teardown(self):
        if self._camera is None or self._context is None:
            print("Already closed gphoto connection")
            return
        print("Closing gphoto connection")
        gp.check_result(gp.gp_camera_exit(self._camera, self._context))
        self._context, self._camera = None, None

    def capture(self):
        if self._context is None or self._camera is None:
            self._setup()
        file_path = gp.check_result(gp.gp_camera_capture(
            self._camera, gp.GP_CAPTURE_IMAGE, self._context))
        print("Took photo")
        prefix = datetime.now().strftime("%Y-%m-%d-%H%M%S-")
        _, target = tempfile.mkstemp(prefix=prefix, suffix=".jpg", dir=self._output_dir)
        camera_file = gp.check_result(gp.gp_camera_file_get(
                self._camera, file_path.folder, file_path.name,
                gp.GP_FILE_TYPE_NORMAL, self._context))
        print("Got file")
        gp.check_result(gp.gp_file_save(camera_file, target))
        print("Saved to {}".format(target))
        return target
