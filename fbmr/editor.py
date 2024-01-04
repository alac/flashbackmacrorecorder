import datetime
import io
import json
import os
from shutil import copyfile
from typing import Tuple, Optional

import cv2
import numpy
import pyjson5
from PIL import Image


class ConfigUtil:
    """Utility functions for editing the Config.json as a json rather than Config, Action, Effect"""

    CONFIG_NAME = "name"
    CONFIG_ACTIONS = "actions"
    CONFIG_SCREENSHOT_SIZE = "screenshot_size"

    ACTION_NAME = "name"

    DIR_CONFIG_ROOT = "configs"

    @staticmethod
    def load_config(config_name):
        with open(ConfigUtil.config_json_path(config_name), "r") as in_file:
            return pyjson5.load(in_file)

    @staticmethod
    def save_config(config_name, config_dict):
        # use json to pretty print
        os.makedirs(ConfigUtil.config_folder_path(config_name), exist_ok=True)
        with io.open(
            ConfigUtil.config_json_path(config_name), "w", encoding="utf-8"
        ) as f:
            f.write(
                json.dumps(config_dict, ensure_ascii=False, sort_keys=True, indent=2)
            )

    @staticmethod
    def config_folder_path(config_name):
        return os.path.join(ConfigUtil.DIR_CONFIG_ROOT, config_name)

    @staticmethod
    def config_json_path(config_name):
        return os.path.join(ConfigUtil.config_folder_path(config_name), "config.json")

    @staticmethod
    def config_json_backup_folder_path(config_name):
        return os.path.join(ConfigUtil.config_folder_path(config_name), "backups")

    @staticmethod
    def config_json_timestamped_backup_path(config_name):
        timestamp = datetime.datetime.now().strftime("%Y %B %d %A %I-%M-%S%p")
        return os.path.join(
            ConfigUtil.config_json_backup_folder_path(config_name),
            f"config_{timestamp}.json",
        )

    @staticmethod
    def write_new_json(config_name):
        data = {
            ConfigUtil.CONFIG_NAME: config_name,
            ConfigUtil.CONFIG_ACTIONS: [],
        }
        ConfigUtil.save_config(config_name, data)

    @staticmethod
    def save_json_with_backup(config_name, config_json_dict):
        # - copy the existing json into the backup folder
        if not os.path.isdir(ConfigUtil.config_json_backup_folder_path(config_name)):
            os.makedirs(ConfigUtil.config_json_backup_folder_path(config_name))
        copyfile(
            ConfigUtil.config_json_path(config_name),
            ConfigUtil.config_json_timestamped_backup_path(config_name),
        )

        # - update the json
        ConfigUtil.save_config(config_name, config_json_dict)

    @staticmethod
    def get_action_names(config_json):
        action_names = []
        for action_dict in config_json[ConfigUtil.CONFIG_ACTIONS]:
            action_names.append(action_dict[ConfigUtil.ACTION_NAME])
        return action_names

    @staticmethod
    def insert_new_action(config_json, action_json):
        # overwrite if name collision
        new_action_name = action_json[ConfigUtil.ACTION_NAME]
        actions_array = config_json[ConfigUtil.CONFIG_ACTIONS]
        for i in range(len(actions_array)):
            if actions_array[i][ConfigUtil.ACTION_NAME] == new_action_name:
                actions_array[i] = action_json
                return
        # did not find a matching action, insert at end
        actions_array.append(action_json)

    @staticmethod
    def get_action_json(config_json, action_name):
        for action_dict in config_json[ConfigUtil.CONFIG_ACTIONS]:
            if action_dict[ConfigUtil.ACTION_NAME] == action_name:
                return action_dict
        return None

    @staticmethod
    def get_screenshot_size(config_json) -> Optional[Tuple[int, int]]:
        return config_json.get(ConfigUtil.CONFIG_SCREENSHOT_SIZE, None)

    @staticmethod
    def set_screenshot_size(config_json, screenshot_size: Tuple[int, int]):
        config_json[ConfigUtil.CONFIG_SCREENSHOT_SIZE] = screenshot_size


def all_config_names(config_root: str = ConfigUtil.DIR_CONFIG_ROOT):
    config_names = []
    for d in os.listdir(config_root):
        if os.path.isdir(os.path.join(config_root, d)):
            if os.path.isfile(os.path.join(config_root, d, "config.json")):
                config_names.append(d)
    return config_names


def interactive_crop_screenshot_and_save(
    pil_image, filename_stem, config_name, save_original=True
):
    """Use OpenCV to interactively crop an image and then save the result."""

    sc = pil_image
    ss_name = filename_stem
    if len(ss_name) == 0:
        ss_name = "NO_NAME_PROVIDED"

    # crop screenshot with OpenCV
    numpy_image = cv2.cvtColor(numpy.array(sc), cv2.COLOR_RGB2BGR)
    region = cv2.selectROI(numpy_image, False)  # fromCenter=False
    x, y, w, h = region
    numpy_image_crop = numpy_image[int(y) : int(y + h), int(x) : int(x + w)]
    # Display cropped image
    cv2.imshow("Result", numpy_image_crop)
    cv2.waitKey(0)

    timestamp = datetime.datetime.now().strftime("%Y %B %d %A %I-%M-%S%p")
    filename_stem = f"{ss_name}_x{x}_y{y}_w{w}_h{h}_{timestamp}"
    filename_region = filename_stem + "_r.png"

    folder = ConfigUtil.config_folder_path(config_name)
    if save_original:
        filename_ss = filename_stem + "_ORIG.png"
        sc.save(os.path.join(folder, filename_ss))
    region_image = Image.fromarray(cv2.cvtColor(numpy_image_crop, cv2.COLOR_BGR2RGB))
    region_image.save(os.path.join(folder, filename_region))


def update_action_and_save_json(
    config_name, config_json_dict, action_index_to_update, action_json_str
):
    """Used when a 'config' needs either a new action inserted, or an old action updated."""
    if config_name is None:
        print("save_json called, but no config loaded")
        return
    if config_json_dict is None:
        print("save_json called, but no config json loaded")
        return

    # - inject the updated ActionJson into the Config at the right place
    new_action_dict = pyjson5.loads(action_json_str)
    if action_index_to_update is None:
        print("save_json called, but no action being edited")
        return

    actions = config_json_dict[ConfigUtil.CONFIG_ACTIONS]
    if action_index_to_update < len(actions):
        actions[action_index_to_update] = new_action_dict
    else:
        actions.append(new_action_dict)

    # - update the json
    ConfigUtil.save_json_with_backup(config_name, config_json_dict)
