from typing import Optional
from PIL import Image

from fbmr.devicetypes import adb_alt_device, windows_app_device, device


class WindowsAndroidDevice(device.WindowsAppInterfaceDevice, device.ADBInterfaceDevice):
    """
    WindowsAndroidDevice is similar to StreamingAndroidDevice except that it uses an existing instance
    of the Scrcpy app. The upsides of using this are:
    - Android-aware version of WindowsAppDevice, that can be used in MacroRecorder.
    """

    def __init__(self, capture_size, adb_flags, crop_settings=None, window_title_regexes=None):
        self.target_size = capture_size
        self.adbDevice = adb_alt_device.ADBAltDevice(self.target_size, adb_flags)
        self.windows_app_device = windows_app_device.WindowsAppDevice(self.target_size, crop_settings=crop_settings,
                                                                        window_title_regexes=window_title_regexes)

    @property
    def window_manager(self):
        return self.windows_app_device.window_manager

    @property
    def crop_settings(self):
        return self.windows_app_device.crop_settings

    @crop_settings.setter
    def crop_settings(self, x):
        self.windows_app_device.crop_settings = x

    @property
    def scale_x(self):
        return self.windows_app_device.scale_x

    @property
    def scale_y(self):
        return self.windows_app_device.scale_y

    def recompute_size(self, delay=0):
        self.adbDevice.recompute_size(delay=delay)

    def screen_capture_raw(self, crop_settings=None):
        # type: (Optional[tuple[int]]) -> Image
        return self.windows_app_device.screen_capture_raw(crop_settings=crop_settings)

    def screen_capture(self):
        # type: () -> Image
        return self.windows_app_device.screen_capture()

    def warn_if_screenshot_has_borders(self):
        # type: () -> bool
        return self.windows_app_device.warn_if_screenshot_has_borders()

    def click(self, x, y):
        # type: (int, int) -> None
        self.adbDevice.click(x, y)

    def swipe(self, x, y, x2, y2, duration):
        # type: (int, int, int, int, float) -> None
        """x and y are from the top corner"""
        self.adbDevice.swipe(x, y, x2, y2, duration)

    def open_app(self, app_bundle_id):
        self.adbDevice.open_app(app_bundle_id)

    def close_app(self, app_bundle_id):
        self.adbDevice.close_app(app_bundle_id)

    def press_back_button(self):
        self.adbDevice.press_back_button()

    def press_home_button(self):
        self.adbDevice.press_home_button()
