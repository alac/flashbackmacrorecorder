"""
macro_recorder.py
Records clicks/drags on the selected window + screenshots as a Config that can be played back later.
Assumes that actions should be chained together.
Needs to be run as a module "python -m tools.macro_recorder"
"""

import argparse
import datetime
import os
import re
import time
from queue import Queue, Empty
from threading import Thread, Lock
from typing import Optional

import cv2
import numpy as np
import win32api
from PIL import ImageDraw, Image

from fbmr.devices import all_device_constructors
from fbmr.conditions import load_condition
from fbmr.editor import ConfigUtil
from fbmr.devicetypes.windows_app_device import transform_point_from_desktop_to_window, \
    transform_point_from_window_to_target_size
from fbmr.devicetypes.device import WindowsAppInterfaceDevice
from fbmr.utils.settings import settings


CLICK_MAX_MOVEMENT = 8  # 8 pixels in target screen coordinates
CLICK_MAX_DURATION = 1.0  # 1 second
DRAG_ENABLED = True
THREADING = True

EXIT_COMMAND = "EXIT"


class ConfigRecorder:
    def __init__(self, config_name, device, action_prefix):
        self._config_json = {}
        self._config_name = config_name
        self._device = device
        self._actions_added = []
        self._last_action_added_time = 0
        self._last_screenshot = None
        self._next_action_id_number = 0
        self._action_prefix = action_prefix
        self.lock = Lock()

    def create_or_load(self):
        folder_path = ConfigUtil.config_folder_path(self._config_name)
        json_path = ConfigUtil.config_json_path(self._config_name)

        # if the json doesn't exist, make one
        is_new = not os.path.exists(json_path)
        if is_new:
            if not os.path.isdir(folder_path):
                os.makedirs(folder_path)
            ConfigUtil.write_new_json(self._config_name)

        # load the config
        data = ConfigUtil.load_config(self._config_name)
        if not data:
            print("load_config: got empty data instead of a json")
            return
        self._config_json = data
        print("load_config: loaded json")
        print(f"""####################### JSON BEGIN #######################
{self._config_json}
####################### JSON END #######################
""")

        largest_id_no = 0
        escaped_prefix = re.escape(self._action_prefix)
        for action_name in ConfigUtil.get_action_names(self._config_json):
            match = re.match(escaped_prefix + r"_(\d+)", action_name)
            if not match:
                continue
            largest_id_no = max(int(match.group(1)), largest_id_no)
        self._next_action_id_number = 1 + largest_id_no

    def consume_next_action_name(self):
        with self.lock:
            new_action_name = f"{self._action_prefix}_{self._next_action_id_number}"
            self._next_action_id_number += 1
        return new_action_name

    def config_folder(self):
        return ConfigUtil.config_folder_path(self._config_name)

    def write_config_with_new_action(self, new_action_dict, screenshot):
        with self.lock:
            ConfigUtil.insert_new_action(self._config_json, new_action_dict)

            # set the advance_if_condition default in case there's no next action
            new_inverse_condition = new_action_dict["conditions"][0].copy()
            new_inverse_condition["type"] = "NotSubimageCondition"
            new_action_dict["advance_if_condition"] = new_inverse_condition
            new_action_dict["cooldown"] = 1.0

            # set the advance_if_condition to either:
            # a. wait for the current action to become invalid
            # b. wait for the next action to become valid
            new_action_name = new_action_dict["name"]
            if self._actions_added:
                last_action_dict = ConfigUtil.get_action_json(self._config_json, self._actions_added[-1])
                last_action_dict["next_action_names"] = [new_action_name]
                if self._last_action_added_time != 0:
                    last_action_dict["cooldown"] = float(time.time() - self._last_action_added_time)
                folder_path = ConfigUtil.config_folder_path(self._config_name)
                last_condition = load_condition(last_action_dict["conditions"][0], folder_path)
                this_condition = load_condition(new_action_dict["conditions"][0], folder_path)
                if not last_condition.is_valid(screenshot, {}, {}):
                    # If actionX's click image does not appear in actionX+1's screenshot
                    # Avoid advancing to X+1 until X's click image disappears
                    print("using previous screenshots condition as an advanceIfCondition")
                    inverse_condition = last_action_dict["conditions"][0].copy()
                    inverse_condition["type"] = "NotSubimageCondition"
                    last_action_dict["advance_if_condition"] = inverse_condition
                elif self._last_screenshot and not this_condition.is_valid(self._last_screenshot, {}, {}):
                    # If actionX+1's click image does not appear in actionX's screenshot
                    # Avoid advancing to X+1 until X's actionX+1's click image appears
                    print("using current screenshots condition as an advanceIfCondition")
                    next_condition_dict = new_action_dict["conditions"][0].copy()
                    last_action_dict["advance_if_condition"] = next_condition_dict
                else:
                    # actionX and actionX+1's conditions are simulatenously valid when either should
                    # occur, so the default "advance_if_condition" would lock up execution...
                    del last_action_dict["advance_if_condition"]
            self._actions_added.append(new_action_name)
            self._last_action_added_time = time.time()

            # save the json
            ConfigUtil.save_json_with_backup(self._config_name, self._config_json)
            print(f"Wrote new action: {new_action_name}")

    def check_screenshot_size(self, device):
        old_ss_size = ConfigUtil.get_screenshot_size(self._config_json)
        new_ss_size = device.screen_capture_raw().size

        if old_ss_size is None:
            ConfigUtil.set_screenshot_size(self._config_json, new_ss_size)
            return

        # normalize the size, so that we can check ratios "apples to apples"
        norm_new_ss_size = ((new_ss_size[0] * old_ss_size[1]) / new_ss_size[1]), old_ss_size[1]

        ratio_old = float(old_ss_size[0]) / old_ss_size[1]
        ratio_new = float(new_ss_size[0]) / new_ss_size[1]

        if abs(ratio_old - ratio_new) > .01:
            print(f"Check your window size: current screenshot ratio {norm_new_ss_size} does not match old screenshot ratio {old_ss_size}")


class ClickEvent:
    def __init__(self, screenshot, position_in_target_xy, start_timestamp, device, is_right=False):
        self.screenshot = screenshot
        self.start_position_in_target_xy = position_in_target_xy
        self.start_timestamp = start_timestamp
        self.end_position_in_target_xy = None
        self.end_timestamp = 0
        self.device = device
        self.is_right = is_right

    @staticmethod
    def start_event_if_click_in_window(device, is_right=False):
        """
        Check whether the click occurred in the target window.
        If it did, create a ClickEvent with information that we'll need for mouse-release.
        """
        ts = time.time()
        # get the position of the button
        x, y = win32api.GetCursorPos()
        in_window, window_xy = transform_point_from_desktop_to_window(device.window_manager, (x, y))
        if not in_window:
            return None

        # take a screenshot
        screenshot = device.screen_capture()

        x, y = transform_point_from_window_to_target_size(
            device.crop_settings,
            (device.scale_x, device.scale_y),
            window_xy)
        position_in_target_xy = (x, y)
        return ClickEvent(screenshot, position_in_target_xy, ts, device, is_right)

    def released(self):
        # get the position of the button
        x, y = win32api.GetCursorPos()
        in_window, window_xy = transform_point_from_desktop_to_window(self.device.window_manager, (x, y))
        if not in_window:  # click cancelled
            return False

        x2, y2 = transform_point_from_window_to_target_size(
            self.device.crop_settings,
            (self.device.scale_x, self.device.scale_y),
            window_xy)
        self.end_position_in_target_xy = (x2, y2)
        self.end_timestamp = time.time()
        return True

    def commit_action(self, config_recorder):
        x, y = self.start_position_in_target_xy
        x2, y2 = self.end_position_in_target_xy
        duration = self.end_timestamp - self.start_timestamp
        if DRAG_ENABLED and ((abs(x - x2) + abs(y - y2)) > CLICK_MAX_MOVEMENT or duration > CLICK_MAX_DURATION):
            self.commit_drag(config_recorder)
        else:
            self.commit_click(config_recorder)

    def commit_click(self, config_recorder):
        new_action_name = config_recorder.consume_next_action_name()

        sc = self.screenshot
        sc_width, sc_height = sc.size
        crop_x, crop_y = settings.get_macrorecorder_click_image_size()

        def clamp(val, low, high):
            return max(min(val, high), low)

        x, y = self.start_position_in_target_xy
        cx = clamp(x, crop_x / 2, sc_width - crop_x / 2)
        cy = clamp(y, crop_y / 2, sc_height - crop_y / 2)
        # print(f"clamp xy {cx} {cy}")
        crop_region = (float(cx - crop_x / 2), float(cy - crop_x / 2), float(cx + crop_x / 2),
                       float(cy + crop_x / 2))
        # print(f"crop region {crop_region}")
        sc_cropped = sc.crop(crop_region)

        timestamp = datetime.datetime.now().strftime("%Y %B %d %A %I-%M-%S%p")
        filename_stem = f"{new_action_name}_xy1xy2{crop_region}_{timestamp}"
        filename_region = filename_stem + "_tap.png"
        folder = config_recorder.config_folder()
        sc.save(os.path.join(folder, filename_stem + "_orig.png"))
        sc_cropped.save(os.path.join(folder, filename_region))
        sc_outline = sc.copy()
        sc_outline_draw = ImageDraw.Draw(sc_outline, "RGBA")
        sc_outline_draw.rectangle(crop_region, outline=(0, 255, 255, 127), width=3)
        sc_outline.save(os.path.join(folder, filename_stem + "_outline.png"))

        tap_xy_in_image = [x - crop_region[0], y - crop_region[1]]
        # inject a new action into the json
        new_action_dict = {
            "name": new_action_name,
            "conditions": [
                {
                    "type": "SubimageCondition",
                    "image_path": filename_region,
                    "threshold": 70,
                    "weight": 1.0,
                    "intended_region": crop_region
                }
            ],
            "effects": [
                {
                    "type": "ClickSubimageEffect",
                    "image_path": filename_region,
                    "intended_region": crop_region,
                    "tap_xy_in_image": tap_xy_in_image
                }
            ],
            "is_enabled": True
        }

        config_recorder.write_config_with_new_action(new_action_dict, sc)

    def commit_drag(self, config_recorder):
        new_action_name = config_recorder.consume_next_action_name()

        sc = self.screenshot
        sc_width, sc_height = sc.size
        crop_x, crop_y = settings.get_macrorecorder_click_image_size()

        def clamp(val, low, high):
            return max(min(val, high), low)

        x, y = self.start_position_in_target_xy
        cx = clamp(x, crop_x / 2, sc_width - crop_x / 2)
        cy = clamp(y, crop_y / 2, sc_height - crop_y / 2)
        # print(f"clamp xy {cx} {cy}")
        crop_region = (float(cx - crop_x / 2), float(cy - crop_y / 2), float(cx + crop_x / 2),
                       float(cy + crop_y / 2))
        # print(f"crop region {crop_region}")
        sc_cropped = sc.crop(crop_region)

        timestamp = datetime.datetime.now().strftime("%Y %B %d %A %I-%M-%S%p")
        filename_stem = f"{new_action_name}_xy1xy2{crop_region}_{timestamp}"
        filename_region = filename_stem + "_tap.png"
        folder = config_recorder.config_folder()
        sc.save(os.path.join(folder, filename_stem + "_orig.png"))
        sc_cropped.save(os.path.join(folder, filename_region))
        sc_outline = sc.copy()
        sc_outline_draw = ImageDraw.Draw(sc_outline, "RGBA")
        sc_outline_draw.rectangle(crop_region, outline=(0, 255, 255, 127), width=3)
        sc_outline_np = np.array(sc_outline)
        x2, y2 = self.end_position_in_target_xy
        sc_outline_np = cv2.arrowedLine(sc_outline_np, (x, y), (x2, y2), (255, 255, 0), 3)
        sc_outline = Image.fromarray(sc_outline_np)
        sc_outline.save(os.path.join(folder, filename_stem + "_outline.png"))

        tap_xy_in_image = [x - crop_region[0], y - crop_region[1]]
        movement_amount = [x2 - x, y2 - y]
        duration = self.end_timestamp - self.start_timestamp
        # inject a new action into the json
        new_action_dict = {
            "name": new_action_name,
            "conditions": [
                {
                    "type": "SubimageCondition",
                    "image_path": filename_region,
                    "threshold": 70,
                    "weight": 1.0,
                    # "intended_region":crop_region
                }
            ],
            "effects": [
                {
                    "type": "DragSubimageEffect",
                    "image_path": filename_region,
                    # "intended_region":crop_region,
                    "tap_xy_in_image": tap_xy_in_image,
                    "movement_amount": movement_amount,
                    "duration": duration
                }
            ],
            "is_enabled": True
        }

        config_recorder.write_config_with_new_action(new_action_dict, sc)


def log_click(device, button_name):
    x, y = win32api.GetCursorPos()
    in_window, window_xy = transform_point_from_desktop_to_window(device.window_manager, (x, y))
    base = f"{button_name} Pressed: {x}, {y}"
    if in_window:
        print(f"{base} click in window at {window_xy}", end='\r', flush=True)
    else:
        print(f"{base} click not in window", end='\r', flush=True)


def consume_commit_events(q, config_recorder):
    while True:
        commit_event = q.get()
        commit_event.commit_action(config_recorder)
        q.task_done()


def record_macro(config_name: str, device_name: str, action_prefix: str = "click",
                 command_queue: Optional[Queue] = None, feedback_queue: Optional[Queue] = None):
    print("Preparing to capture")

    d = all_device_constructors()[device_name]()
    assert isinstance(d, WindowsAppInterfaceDevice), "MacroRecorder relies on reading data from a Windows application."
    recorder = ConfigRecorder(config_name, d, action_prefix)
    recorder.create_or_load()
    recorder.check_screenshot_size(d)

    # check for a black border indicating that the window is mis-sized.
    d.warn_if_screenshot_has_borders()

    # Tracking a ClickEvent has three steps: mouse down, mouse up, saving to config.
    # In testing, durations are <.03, 0, and <.5 seconds, which seems thread worthy.
    commit_queue = Queue(maxsize=0)
    worker = Thread(target=consume_commit_events, args=(commit_queue, recorder))
    worker.daemon = True
    worker.start()

    def is_left_click_down():
        return win32api.GetKeyState(0x01) < 0

    def is_right_click_down():
        return win32api.GetKeyState(0x02) < 0

    print("Ready to capture")

    click_event = None
    left_click_down = is_left_click_down()
    right_click_down = is_right_click_down()
    while True:
        try:
            command = command_queue.get_nowait()
            if command == EXIT_COMMAND:
                break
        except Empty:
            pass

        if left_click_down != is_left_click_down():
            left_click_down = not left_click_down
            if click_event is None:
                if left_click_down:
                    log_click(d, "Left Button")
                    click_event = ClickEvent.start_event_if_click_in_window(d, False)
            elif not click_event.is_right:
                if not left_click_down:
                    print('Left Button Released', end='\r', flush=True)
                    should_commit = click_event.released()
                    if should_commit:
                        if THREADING:
                            commit_queue.put(click_event)
                        else:
                            click_event.commit_action(recorder)
                    click_event = None
        if right_click_down != is_right_click_down():
            right_click_down = not right_click_down
            if click_event is None:
                if right_click_down:
                    log_click(d, "Right Button")
                    click_event = ClickEvent.start_event_if_click_in_window(d, True)
            elif click_event.is_right:
                if not right_click_down:
                    print('Right Button Released', end='\r', flush=True)
                    should_commit = click_event.released()
                    if should_commit:
                        if THREADING:
                            commit_queue.put(click_event)
                        else:
                            click_event.commit_action(recorder)
        time.sleep(0.001)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('config_name', help="The config we want to write to.", type=str)
    parser.add_argument("device_name", help="the shorthand name for the device to use; specified in devices.py", type=str)
    args = parser.parse_args()
    record_macro(args.config_name, args.device_name)
