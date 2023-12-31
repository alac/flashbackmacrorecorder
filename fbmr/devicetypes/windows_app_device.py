import math
import pyautogui
import re
import win32gui
import win32ui
import logging
from PIL import Image
from ctypes import windll
from random import randint
from typing import Optional

from fbmr.devicetypes import device

# windows constants
PW_CLIENTONLY = 1
PW_RENDERFULLCONTENT = 2


def log(message: str):
    logging.getLogger("fbmr_logger").debug(f"{__name__}: {message}")


class WindowsAppDevice(device.WindowsAppInterfaceDevice):
    """WindowsAppDevice communicates with a running Windows application via WINDOWS apis to capture and click.
    Uses windll.user32.PrintWindow, which relies on _the app_ implementing screenshot behavior.
    """

    def __init__(
        self, target_size=(720, 1280), crop_settings=None, window_title_regexes=None
    ):
        """
        crop_settings = (left, top, right, bottom) relative to their own edge instead of
            being TOP-LEFT and BOTTOM-RIGHT points relative to the TOP-LEFT corner.
        """
        self._window_manager = WindowManager()
        self.target_size = target_size
        self._scale_x = 1.0
        self._scale_y = 1.0

        if not window_title_regexes:
            window_title_regexes = []

        found = False
        for window_title_regex in window_title_regexes:
            # noinspection PyBroadException
            try:
                self.window_manager.find_window_wildcard(window_title_regex)
                found = True
            except Exception:
                pass

        if not found:
            raise ValueError("SRCCPYDevice could not find a window")

        # init crop settings
        if crop_settings:
            self._crop_settings = crop_settings
        else:
            _, _, im = screenshot_window(
                self.window_manager,
                None,  # target_size needs to be None so that cropping can occur without scaling
                crop_settings=None,
            )
            if crop_settings == "infer":
                self._crop_settings = infer_cropping_and_check(im, target_size)
            else:
                # crop_settings = NONE works, but the ScreenshotTool benefits from exposing the 'natural crop'
                self._crop_settings = (0, 0, 0, 0)

        # init scaling
        self._compute_size()

    @property
    def window_manager(self):
        return self._window_manager

    @property
    def crop_settings(self):
        return self._crop_settings

    @crop_settings.setter
    def crop_settings(self, x):
        self._crop_settings = x

    @property
    def scale_x(self):
        return self._scale_x

    @property
    def scale_y(self):
        return self._scale_y

    def _compute_size(self):
        self._scale_x, self._scale_y, im = screenshot_window(
            self._window_manager, self.target_size, crop_settings=self.crop_settings
        )

    def recompute_size(self):
        self._compute_size()

    def screen_capture_raw(self, crop_settings=None):
        # type: (Optional[tuple[int,int,int,int]]) -> Image
        self._scale_x, self._scale_y, im = screenshot_window(
            self._window_manager,
            None,  # target_size
            crop_settings=crop_settings,
        )
        return im

    def screen_capture(self):
        # type: () -> Image
        self._scale_x, self._scale_y, im = screenshot_window(
            self._window_manager, self.target_size, crop_settings=self._crop_settings
        )
        return im

    def warn_if_screenshot_has_borders(self):
        sc = self.screen_capture_raw(crop_settings=self._crop_settings)
        crop_settings = infer_cropping(sc)
        if crop_settings != (0, 0, 0, 0):
            logging.getLogger("fbmr_logger").warning(
                f"WARNING: screenshot has black borders\nScreenshots may be inaccurate.\nBorders detected (left, top, "
                f"right, bottom) {crop_settings}"
            )
            return True
        return False

    def click(self, x, y):
        # type: (int, int) -> None
        """x and y are from the top corner"""
        py_click(
            self._window_manager,
            (x, y),
            self._crop_settings,
            (self._scale_x, self._scale_y),
        )

    def swipe(self, x, y, x2, y2, duration):
        # type: (int, int, int, int, float) -> None
        py_swipe(
            self._window_manager,
            (x, y),
            (x2, y2),
            duration,
            self._crop_settings,
            (self._scale_x, self._scale_y),
        )


def transform_point_to_window(crop_settings, scale_xy, point_xy):
    """Transforms a point from the 'target_size' coordinate system to app window.
    E.g. (0, 0) would be the TOP LEFT of the app window.
    """
    x, y = point_xy

    # undo the scaling
    sx, sy = scale_xy
    x = sx * x
    y = sy * y

    left, top, right, bottom = crop_settings
    return x + left, y + top


def transform_point_from_desktop_to_window(
    window_manager,
    point_xy,
):
    """Transforms a point from desktop coordinates to window coordinates.
    Checks if window is focused.
    @return: (bool 'was in window', (x, y) point)
    """
    x, y = point_xy
    w = window_manager

    cx, cy = win32gui.ScreenToClient(w.window_handle, (x, y))
    # x2, y2 = win32gui.ClientToScreen(w._handle, (cx, cy))

    left, top, right, bot = win32gui.GetClientRect(
        w.window_handle
    )  # handles title bar/borders
    if cx < left or cx > right:
        return False, (0, 0)
    if cy < top or cy > bot:
        return False, (0, 0)

    fg_window = win32gui.GetForegroundWindow()
    return fg_window == w.window_handle, (cx, cy)


def transform_point_from_window_to_target_size(
    crop_settings,
    scale_xy,
    window_xy,
):
    wx, wy = window_xy
    left, top, right, bottom = crop_settings

    tx, ty = wx - left, wy - top

    sx, sy = scale_xy
    tx, ty = tx / sx, ty / sy
    return int(tx), int(ty)


class WindowManager:
    """Encapsulates some calls to the winapi for window management"""

    def __init__(self):
        """Constructor"""
        self.window_handle = None
        self._window_title = None
        self._all_window_titles = []
        self._all_handles_by_title = {}

    def find_window(self, class_name, window_name=None):
        """find a window by its class_name"""
        self.window_handle = win32gui.FindWindow(class_name, window_name)

    def _window_enum_callback(self, hwnd, wildcard):
        """Pass to win32gui.EnumWindows() to check all the opened windows"""
        window_title = str(win32gui.GetWindowText(hwnd))
        if re.match(wildcard, window_title) is not None:
            self.window_handle = hwnd
            self._window_title = window_title

    def find_window_wildcard(self, wildcard):
        self.window_handle = None
        win32gui.EnumWindows(self._window_enum_callback, wildcard)

    def set_foreground(self):
        """put the window in the foreground"""
        win32gui.SetForegroundWindow(self.window_handle)

    def get_window_title(self):
        if self._window_title is None:
            raise ValueError("get_window_text called on invalid window")

        return self._window_title

    def _collect_window_titles_enum_callback(self, hwnd, _wildcard):
        """Pass to win32gui.EnumWindows() to check all the opened windows"""
        window_title = str(win32gui.GetWindowText(hwnd))
        if window_title not in self._all_handles_by_title:
            self._all_window_titles.append(window_title)
            self._all_handles_by_title[window_title] = hwnd

    def all_window_titles(self):
        self._all_window_titles = []
        self._all_handles_by_title = {}
        win32gui.EnumWindows(self._collect_window_titles_enum_callback, "*")
        return sorted(self._all_window_titles)

    def choose_window(self, window_title):
        if window_title in self._all_handles_by_title:
            self._window_title = window_title
            self.window_handle = self._all_handles_by_title[window_title]
        else:
            raise ValueError(f"Invalid WindowTitle: {window_title}")


def screenshot_window(
    window_manager,
    target_size,
    crop_settings=None,
):
    """
    Grab a screenshot of a window.

    Depends on 'windll.user32.PrintWindow' which depends on the window to screenshot itself.
    This is how the behavior varies for the 'flags' argument.
    | App             | flag=0 | flag=PW_CLIENTONLY|PW_RENDERFULLCONTENT |
    |-----------------|--------|-----------------------------------------|
    | scrcpy          | Works  | Works                                   |
    | NIKKE           | Blank  | Blank                                   |
    | Persona 5 Royal | Blank  | Works                                   |

    Args:
        window_manager: The window manager object.
        target_size: The desired size of the screenshot.
        crop_settings: A tuple of four integers (left, top, right, bottom) specifying the
            portion of the screenshot to crop.

    Returns:
        A tuple of three values:
            - The scale factor applied to the screenshot to account for DPI scaling.
            - The cropped and resized screenshot image.
    """

    # Grab window reference and make active
    w = window_manager
    hwnd = w.window_handle

    dpi_scale = windll.user32.GetDpiForWindow(hwnd) / 96.0

    # "GetClientRect() does not include the border and title bar."
    # Bounding box relative to client area (e.g. left and top are always 0)
    left, top, right, bottom = win32gui.GetClientRect(hwnd)

    width = int((right - left) * dpi_scale)
    height = int((bottom - top) * dpi_scale)

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(save_bitmap)
    result = windll.user32.PrintWindow(
        hwnd, save_dc.GetSafeHdc(), PW_CLIENTONLY | PW_RENDERFULLCONTENT
    )

    bmp_info = save_bitmap.GetInfo()
    bmp_str = save_bitmap.GetBitmapBits(True)

    im = Image.frombuffer(
        "RGB",
        (bmp_info["bmWidth"], bmp_info["bmHeight"]),
        bmp_str,
        "raw",
        "BGRX",
        0,
        1,
    )

    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    scale_x, scale_y = (1.0, 1.0)

    if result == 1:
        # Do we need to "correct" for DPI scaling before cropping?
        # Should we pre-scale by DPI scale so that the rest of the app can
        # be DPI agnostic?
        if dpi_scale != 1.0:
            simulated_size = (width, height)
            im = im.resize(simulated_size, Image.ANTIALIAS)

        if crop_settings is not None:
            # Transform from edge relative to TOP-LEFT only points, which is what
            # Pillow does. The top-left and bottom-right coordinates of the
            # rectangle (left, top, right, bottom)
            left, top, right, bottom = crop_settings
            right = im.width - right
            bottom = im.height - bottom
            crop_settings = (left, top, right, bottom)
            im = im.crop(crop_settings)

        if target_size:
            target_width, target_height = target_size
            if im.size[0] != target_width or im.size[1] != target_height:
                scale_x = im.size[0] / float(target_width)
                scale_y = im.size[1] / float(target_height)
                im = im.resize(target_size, Image.ANTIALIAS)

    return scale_x, scale_y, im


def infer_cropping_and_check(image, target_size):
    w, h = image.size

    l, t, r, b = infer_cropping(image)
    nw = w - l - r
    nh = h - t - b

    log(
        "crop ratios {0} desired {1}".format(
            (float(nw) / nh), float(target_size[0]) / target_size[1]
        )
    )

    if abs((float(nw) / nh) - float(target_size[0]) / target_size[1]) > 0.04:
        log(f"Crop did not have desired ratio:, ({l}, {t}, {r}, {b})")
        return 0, 0, 0, 0
    return l, t, r, b


def infer_cropping(image, has_window_border=False):
    """
    returns the top-left and bottom-right coordinates of the rectangle
    (left, top, right, bottom)
    """
    rgb_image = image.convert("RGB")
    w, h = rgb_image.size

    blackness = 1

    def is_black(x, y):
        r, g, b = rgb_image.getpixel((x, y))
        all_equal = r == g and r == b
        return all_equal and r < blackness

    def is_not_black(x, y):
        r, g, b = rgb_image.getpixel((x, y))
        return r > blackness or g > blackness or b > blackness

    def find_z_from_a_to_b_with_delta(z, a, b, d):
        """
        walk from a to b, in increments of d.
        when you find z stop.
        if you don't find z, return b.
        """
        x, y = a
        fx, fy = b
        dx, dy = d

        # randomize along the direction that you're not moving
        randomize_x = d[0] == 0
        randomize_y = d[1] == 0

        trials = 50
        while x != fx or y != fy:
            successes = 0
            for i in range(trials):
                test_x = x
                test_y = y
                if randomize_x:
                    test_x = randint(0, w - 1)
                if randomize_y:
                    test_y = randint(0, h - 1)

                if z(test_x, test_y):
                    successes += 1

            if successes > 0:
                return x, y

            x += dx
            y += dy
        log("infer_cropping walked to center")
        raise ValueError("Couldn't find intended pixel value")

    max_x, max_y = w - 1, h - 1
    top_center = (int(w / 2), 0)
    bottom_center = (int(w / 2), max_y)
    left_center = (0, int(h / 2))
    right_center = (max_x, int(h / 2))

    center_center = (int(w / 2), int(h / 2))

    # walk from the edge to the center looking for the transition from black pixels to non-black pixels
    # if you never find that transition, you were already at the edge and have gone too far
    # if there is a window border, you additionally have to search for the first black pixel

    try:
        if has_window_border:
            top = find_z_from_a_to_b_with_delta(
                is_black, top_center, center_center, (0, 1)
            )
            top = find_z_from_a_to_b_with_delta(
                is_not_black, top, center_center, (0, 1)
            )
        else:
            top = find_z_from_a_to_b_with_delta(
                is_not_black, top_center, center_center, (0, 1)
            )
    except ValueError:
        top = top_center

    try:
        if has_window_border:
            left = find_z_from_a_to_b_with_delta(
                is_black, left_center, center_center, (1, 0)
            )
            left = find_z_from_a_to_b_with_delta(
                is_not_black, left, center_center, (1, 0)
            )
        else:
            left = find_z_from_a_to_b_with_delta(
                is_not_black, left_center, center_center, (1, 0)
            )
    except ValueError:
        left = left_center

    try:
        if has_window_border:
            right = find_z_from_a_to_b_with_delta(
                is_black, right_center, center_center, (-1, 0)
            )
            right = find_z_from_a_to_b_with_delta(
                is_not_black, right, center_center, (-1, 0)
            )
        else:
            right = find_z_from_a_to_b_with_delta(
                is_not_black, right_center, center_center, (-1, 0)
            )
    except ValueError:
        right = right_center

    try:
        if has_window_border:
            bottom = find_z_from_a_to_b_with_delta(
                is_black, bottom_center, center_center, (0, -1)
            )
            bottom = find_z_from_a_to_b_with_delta(
                is_not_black, bottom, center_center, (0, -1)
            )
        else:
            bottom = find_z_from_a_to_b_with_delta(
                is_not_black, bottom_center, center_center, (0, -1)
            )
    except ValueError:
        bottom = bottom_center

    return left[0], top[1], max_x - right[0], max_y - bottom[1]


def get_client_window_relative_to_screen(hwnd):
    """Returns the client area of a window relative to the screen."""
    rect = win32gui.GetWindowRect(hwnd)
    client_rect = win32gui.GetClientRect(hwnd)
    window_offset = math.floor(((rect[2] - rect[0]) - client_rect[2]) / 2)
    title_offset = ((rect[3] - rect[1]) - client_rect[3]) - window_offset
    return (
        rect[0] + window_offset,
        rect[1] + title_offset,
        rect[2] - window_offset,
        rect[3] - window_offset,
    )


def preimage_touch_to_screen_touch(
    preimage_touch, dpi_scale, left, top, _right, _bottom
):
    x, y = preimage_touch
    x *= dpi_scale  # DPI scaling factor
    y *= dpi_scale
    x += left
    y += top
    return x, y


def py_click(window_manager, touch_xy, crop_settings, scale_xy):
    dpi_scale = 1.0  # windll.user32.GetDpiForWindow(hwnd) / 96.0

    log("click on phone screen @ {touch_xy}")
    preimage_touch = transform_point_to_window(crop_settings, scale_xy, touch_xy)
    log("click on window client @ {preimage_touch}")

    # grab window reference + make active
    w = window_manager
    hwnd = w.window_handle

    left, top, right, bottom = get_client_window_relative_to_screen(hwnd)
    x, y = preimage_touch_to_screen_touch(
        preimage_touch, dpi_scale, left, top, right, bottom
    )
    log(f">>> click on computer screen {x}, {y}")

    pyautogui.moveTo(x, y)
    pyautogui.click(x=x, y=y)


def py_swipe(window_manager, from_xy, to_xy, duration, crop_settings, scale_xy):
    dpi_scale = 1.0  # windll.user32.GetDpiForWindow(hwnd) / 96.0

    log(f"swipe phone screen from @ {from_xy} to {to_xy}")
    preimage_from = transform_point_to_window(crop_settings, scale_xy, from_xy)
    preimage_to = transform_point_to_window(crop_settings, scale_xy, to_xy)
    log(f"swipe window client from @ {preimage_from} to {preimage_to}")

    # grab window reference + make active
    w = window_manager
    hwnd = w.window_handle

    left, top, right, bottom = get_client_window_relative_to_screen(hwnd)
    x, y = preimage_touch_to_screen_touch(
        preimage_from, dpi_scale, left, top, right, bottom
    )
    x2, y2 = preimage_touch_to_screen_touch(
        preimage_to, dpi_scale, left, top, right, bottom
    )
    log(f">>> click on computer screen {x}, {y} to {x2}, {y2}")

    ix, iy = pyautogui.position()

    pyautogui.mouseUp()
    pyautogui.moveTo(x, y)
    if duration == 0:
        pyautogui.mouseDown()
        pyautogui.moveTo(x2, y2)
        pyautogui.mouseUp()
    else:
        pyautogui.dragTo(x2, y2, duration, button="left")

    pyautogui.moveTo(ix, iy)
