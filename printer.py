import time
from io import BytesIO
from uuid import uuid4
from logging import getLogger

from PyOBEX.client import Client

log = getLogger("photobooth.camera")


class Printer:
    config = None
    _client = None

    def __init__(self, config):
        self.config = config["printer"]

    def print(self, image):
        if not self._setup():
            log.debug(
                "Giving up attempting to print because couldn't connect to printer."
            )
            return False
        w, h = self.config.getint("width"), self.config.getint("height")
        log.debug("resizing image to {}x{}...".format(w, h))
        print_image = image.resize((w, h))
        buffer = BytesIO()
        print_image.save(buffer, self.config["format"])
        image_bytes = buffer.getvalue()
        filename = "{}.{}".format(uuid4(), self.config["format"].lower())
        log.debug(
            "sending {} bytes to printer as {}...".format(len(image_bytes), filename)
        )
        self._client.put(filename, image_bytes)
        log.debug("done.")
        self._teardown()
        return True

    def _setup(self):
        log.debug("Connecting to printer...")
        if self._client is not None:
            log.debug("Already connected to printer.")
            return True
        mac = self.config["address"]
        channel = self.config.getint("channel")
        self._client = Client(mac, channel)
        try:
            self._client.connect()
            log.debug("done.")
        except Exception:
            log.exception("Couldn't connect to printer:")
            self._client = None
            return False
        else:
            return True

    def _teardown(self):
        log.debug("Closing printer connection:")
        if self._client is None:
            log.debug("Already closed printer connection.")
            return
        try:
            self._client.disconnect()
        except Exception:
            log.exception("Couldn't close printer connection:")
        else:
            self._client = None
            log.debug("done.")

    def __del__(self):
        self._teardown()
