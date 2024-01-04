import base64
import io
import subprocess
import time

from PIL import Image

from fbmr.devicetypes import device


class ADBDevice(device.ADBInterfaceDevice):
    """ADBDevice communicates with a running Android device using ADB to capture and click.
    Exists for 'minimal dependency' testing, but screen_capture is too slow for any meaningful use (~5 to 15+ seconds).
    """

    def __init__(self, capture_size, adb_flags):
        self.adb_flags = adb_flags
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

    def insert_flags(self, cmd):
        if self.adb_flags:
            return cmd[:1] + self.adb_flags + cmd[1:]

        return cmd

    def screen_capture_raw(self):
        # type: () -> Image
        line = ["adb", "shell", "screencap -p | base64 -w 0"]
        b64_output = subprocess.check_output(self.insert_flags(line))
        raw_output = base64.decodebytes(b64_output)
        fp = io.BytesIO(raw_output)
        return Image.open(fp)

    def screen_capture(self):
        # type: () -> Image
        im = self.screen_capture_raw()
        return im.resize(self.capture_size, Image.ANTIALIAS)

    def click(self, x, y):
        # type: (int, int) -> None
        """x and y are from the top corner"""
        xr = x * self.device_size[0] / self.capture_size[0]
        yr = y * self.device_size[1] / self.capture_size[1]

        line = [
            "adb",
            "shell",
            "input touchscreen tap {0} {1}".format(str(int(xr)), str(int(yr))),
        ]
        print("      adbDevice running {0}".format(line))
        subprocess.check_output(self.insert_flags(line))

    def swipe(self, x, y, x2, y2, duration):
        # type: (int, int, int, int, float) -> None
        """x and y are from the top corner"""
        xr = x * self.device_size[0] / self.capture_size[0]
        yr = y * self.device_size[1] / self.capture_size[1]
        xr2 = x2 * self.device_size[0] / self.capture_size[0]
        yr2 = y2 * self.device_size[1] / self.capture_size[1]

        # 500 ms is a magic number for a 'min duration'
        duration_ms = max(500, int(duration * 1000))

        line = [
            "adb",
            "shell",
            "input",
            "touchscreen",
            "swipe",
            str(int(xr)),
            str(int(yr)),
            str(int(xr2)),
            str(int(yr2)),
            str(duration_ms),
        ]
        print("      adbDevice running {0}".format(line))
        subprocess.check_output(self.insert_flags(line))

    def open_app(self, app_bundle_id):
        line = ["adb", "shell", "monkey", "-p", app_bundle_id, "1"]
        subprocess.check_output(self.insert_flags(line))

    def close_app(self, app_bundle_id):
        line = ["adb", "shell", "input", "keyevent", "KEYCODE_HOME"]
        subprocess.check_output(self.insert_flags(line))

        line = ["adb", "shell", "am", "force-stop", app_bundle_id]
        subprocess.check_output(self.insert_flags(line))

    def press_back_button(self):
        line = ["adb", "shell", "input", "keyevent", "KEYCODE_BACK"]
        subprocess.check_output(self.insert_flags(line))

    def press_home_button(self):
        line = ["adb", "shell", "input", "keyevent", "KEYCODE_HOME"]
        subprocess.check_output(self.insert_flags(line))

    @classmethod
    def devices(cls):
        return [
            str(dev.split(b"\t")[0])[2:-1]
            for dev in subprocess.check_output(["adb", "devices"]).splitlines()
            if dev.endswith(b"\tdevice")
        ]

    @classmethod
    def get_screen_resolution(cls, serial):
        device_info = subprocess.check_output(
            ["adb", "-s", f"{serial}", "shell", "wm size"]
        ).splitlines()
        """
        Expected:
        Physical size: 1440x3040
        Override size: 1080x2280
        """
        physical_size = None
        override_size = None
        for size in device_info:
            if b": " in size:
                wxh_str = size.split(b": ")[1].split(b"x")
                w, h = int(wxh_str[0]), int(wxh_str[1])

                if physical_size is None:
                    physical_size = (w, h)
                if override_size is None:
                    override_size = (w, h)

                if size.startswith(b"Physical"):
                    physical_size = (w, h)
                if size.startswith(b"Override"):
                    override_size = (w, h)
        return {"physical_size": physical_size, "override_size": override_size}

    @classmethod
    def run_tcpip(cls, serial):
        subprocess.check_output(["adb", "-s", f"{serial}", "tcpip", "5555"])
