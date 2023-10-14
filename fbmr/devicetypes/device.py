from PIL import Image
from abc import ABC, abstractmethod


class Device(ABC):
    @abstractmethod
    def screen_capture_raw(self):
        # type: () -> Image
        """
        Captures screen content without scaling to any resolution.
        Not consistent with other methods.
        """
        pass

    @abstractmethod
    def screen_capture(self):
        # type: () -> Image
        """
        Captures screen content and scales to intended resolution.
        Consistent with other methods.
        """
        pass

    @abstractmethod
    def click(self, x, y):
        # type: (int, int) -> None
        pass

    @abstractmethod
    def swipe(self, x, y, x2, y2, duration):
        # type: (int, int, int, int, float) -> None
        pass

    def __enter__(self):
        return self

    def __exit__(self, exception_type, value, traceback):
        hasattr(self, "close") and self.close()


class ADBInterfaceDevice(Device):
    """ADBInterfaceDevice communicates with a running Android device using ADB to capture and click.
    Exists for 'minimal dependency' testing, but screen_capture is too slow for any meaningful use (~5 to 15+ seconds).
    """

    @abstractmethod
    def recompute_size(self, delay=0):
        pass

    @abstractmethod
    def open_app(self, app_bundle_id):
        pass

    @abstractmethod
    def close_app(self, app_bundle_id):
        pass

    @abstractmethod
    def press_back_button(self):
        pass

    @abstractmethod
    def press_home_button(self):
        pass


class WindowsAppInterfaceDevice(Device):
    @abstractmethod
    def window_manager(self):
        pass

    @property
    @abstractmethod
    def crop_settings(self):
        pass

    @crop_settings.setter
    @abstractmethod
    def crop_settings(self, x):
        pass

    @property
    @abstractmethod
    def scale_x(self):
        pass

    @property
    @abstractmethod
    def scale_y(self):
        pass

    @abstractmethod
    def warn_if_screenshot_has_borders(self):
        # type: () -> bool
        pass
