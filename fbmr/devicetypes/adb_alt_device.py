import time

from adbutils import adb
from PIL import Image

from fbmr.devicetypes import device


class ADBAltDevice(device.ADBInterfaceDevice):
    """ADBAltDevice communicates with a running Android device without using ADB to capture and click.
    Exists for 'minimal dependency' testing, but screen_capture is too slow for any meaningful use (~5 to 15+ seconds).
    Compared to ADBDevice, this does not require adb to be installed on the user machine.
    """

    def __init__(self, capture_size, adb_flags):
        self.adb_flags = adb_flags
        assert '-s' in adb_flags
        self.adb = adb.device(serial=adb_flags[adb_flags.index('-s') + 1])
        self._compute_size()

        if capture_size:
            self.capture_size = capture_size
        else:
            self.capture_size = self.device_size

    def _compute_size(self):
        image = self.screen_capture_raw()
        self.device_size = image.size

    def recompute_size(self, delay=0):
        if delay:
            time.sleep(delay)
        self._compute_size()

    def screen_capture_raw(self):
        # type: () -> Image
        return self.adb.screenshot()

    def screen_capture(self):
        # type: () -> Image
        im = self.screen_capture_raw()
        return im.resize(self.capture_size, Image.ANTIALIAS)

    def click(self, x, y):
        # type: (int, int) -> None
        """x and y are from the top corner"""
        xr = x * self.device_size[0] / self.capture_size[0]
        yr = y * self.device_size[1] / self.capture_size[1]
        self.adb.click(xr, yr)

    def swipe(self, x, y, x2, y2, duration):
        # type: (int, int, int, int, float) -> None
        """x and y are from the top corner"""
        xr = x * self.device_size[0] / self.capture_size[0]
        yr = y * self.device_size[1] / self.capture_size[1]
        xr2 = x2 * self.device_size[0] / self.capture_size[0]
        yr2 = y2 * self.device_size[1] / self.capture_size[1]

        # 500 ms is a magic number for a 'min duration'
        duration_ms = max(500, int(duration * 1000))
        self.adb.swipe(int(xr), int(yr), int(xr2), int(yr2), duration_ms)

    def open_app(self, app_bundle_id):
        self.adb.app_start(app_bundle_id)

    def close_app(self, app_bundle_id):
        self.adb.keyevent('KEYCODE_HOME')
        self.adb.app_stop(app_bundle_id)

    def press_back_button(self):
        self.adb.keyevent('KEYCODE_BACK')

    def press_home_button(self):
        self.adb.keyevent('KEYCODE_HOME')

    @classmethod
    def devices(cls):
        return [d.serial for d in adb.device_list()]

    @classmethod
    def get_screen_resolution(cls, serial):
        device_info = adb.device(serial=serial).shell('wm size').splitlines()
        """
        Expected:
        Physical size: 1440x3040
        Override size: 1080x2280
        """
        physical_size = None
        override_size = None
        for size in device_info:
            if b': ' in size:
                wxh_str = size.split(b': ')[1].split(b'x')
                w, h = int(wxh_str[0]), int(wxh_str[1])

                if physical_size is None:
                    physical_size = (w, h)
                if override_size is None:
                    override_size = (w, h)

                if size.startswith(b'Physical'):
                    physical_size = (w, h)
                if size.startswith(b'Override'):
                    override_size = (w, h)
        return {'physical_size': physical_size, 'override_size': override_size}

    @classmethod
    def run_tcpip(cls, serial):
        adb.device(serial=serial).shell('tcpip 5555').splitlines()
