import tomli
import os
from typing import Any

THIS_FILES_FOLDER = os.path.dirname(os.path.realpath(__file__))
ROOT_FOLDER = os.path.join(THIS_FILES_FOLDER, "..", "..")
DEFAULT_SETTINGS = os.path.join(ROOT_FOLDER, "settings.txt")


class SettingsManager:
    def __init__(self, toml_file_path):
        self.toml_file_path = toml_file_path
        self.settings = {}

    def load_settings(self):
        with open(self.toml_file_path, "rb") as f:
            self.settings = tomli.load(f)

    def get_setting(self, setting_name, default_value):
        # type: (str, Any) -> Any
        keys = setting_name.split(".")
        current_dict = self.settings
        for k in keys:
            if k not in current_dict:
                return default_value
            current_dict = current_dict[k]
        return current_dict

    def get_setting_as_str(self, setting_name, default_value):
        # type: (str, str) -> str
        return self.get_setting(setting_name, default_value)

    def get_setting_as_int(self, setting_name, default_value):
        # type: (str, int) -> int
        """
        setting_name = a key in the settings.toml
        default_value = a valid setting
        """
        return self.get_setting(setting_name, default_value)

    def get_setting_as_seconds(self, setting_name, default_value):
        # type: (str, str) -> int
        """
        In the settings.toml, we're supporting durations as a string like "XX days" or "XX hours" or just the # seconds.
        We'll similarly expect the default_value to be of the same form.
        """
        result = self.get_setting(setting_name, default_value)  # type:str
        if " " not in result:
            if result.isnumeric():
                return int(result)
        else:
            value, units = result.strip().split(" ")
            value_int = int(value)
            if units.lower() in ["hour", "hours"]:
                return value_int * 60 * 60
            if units.lower() in ["day", "days"]:
                return value_int * 24 * 60 * 60
        raise ValueError(f"Expected setting {setting_name} to be a string of form 'XX days', 'XX hours' or 'XX' seconds"
                         f", instead got {result}")

    def get_fbmr_action_retry_duration(self):
        # type: () -> int
        return self.get_setting_as_int("fbmr.action_retry_duration", 4)

    def get_macrorecorder_click_image_size(self):
        # type: () -> list[int, int]
        return self.get_setting("MacroRecorder.click_image_size", [50, 50])

    def get_scrcpydevice_capture_fps(self):
        # type: () -> int
        return self.get_setting_as_int("ScrcpyDevice.capture_fps", 10)

    def get_scrcpydevice_capture_bitrate(self):
        # type: () -> int
        return self.get_setting_as_int("ScrcpyDevice.capture_bitrate", 4000000)

    def get_debug_image_expire_time(self):
        # type: () -> int
        return self.get_setting_as_seconds("DebugSettings.debug_image_expire_time", "7 days")

    def get_debug_log_expire_time(self):
        # type: () -> int
        return self.get_setting_as_seconds("DebugSettings.debug_log_expire_time", "7 days")


settings = SettingsManager(DEFAULT_SETTINGS)
settings.load_settings()
