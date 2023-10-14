import subprocess

from fbmr.devicetypes.windows_android_device import WindowsAndroidDevice
from fbmr.devicetypes.windows_app_device import WindowsAppDevice
from fbmr.devicetypes.streaming_android_device import StreamingAndroidDevice
from fbmr.devicetypes.device import Device

import os
from typing import Tuple, Optional, Callable
import tomlkit
import json


THIS_FILES_FOLDER = os.path.dirname(os.path.realpath(__file__))
DEVICE_CONFIG_FOLDER = os.path.join(THIS_FILES_FOLDER, "..", "devices")


def compute_target_size(max_dimension, w, h):
    max_dimension = float(max_dimension)  # don't round to ints

    if w > h:
        targetW = max_dimension
        targetH = h * (targetW / w)
    else:
        targetH = max_dimension
        targetW = w * (targetH / h)

    return (int(targetW), int(targetH)), (float(h) / targetH)


def all_device_constructors(allowed_types: Optional[list[str]] = None):
    configs = all_device_configs()
    constructors = {}
    for config_name in configs:
        if allowed_types and configs[config_name].get("type", None) not in allowed_types:
            continue

        def create(config: dict):
            _valid, device_interface = parse_device_config(config, instantiate=True)
            return device_interface

        constructors[config_name] = lambda x=config_name: create(configs[x])
    return constructors


def parse_device_config(data: dict, instantiate: bool = False) -> Tuple[bool, Optional[Device]]:
    device_type = data.get("type", None)
    if not device_type:
        raise ValueError(f"parse_device_config: data had no device type value. Data: {data}")
    parsers = all_device_config_parsers()
    p = parsers.get(device_type, None)
    if not p:
        raise ValueError(f"parse_device_config: data had unsupported device type value. Received: {device_type}." +
                         f" Valid: {parsers.keys()}")
    if p.validate(data):
        if not instantiate:
            return True, None
        return True, p.initialize(data)
    return False, None


def all_device_configs() -> dict[str, dict]:
    configs = {}
    for f in os.listdir(DEVICE_CONFIG_FOLDER):
        fp = os.path.join(DEVICE_CONFIG_FOLDER, f)
        if os.path.isfile(fp):
            if not f.endswith(".txt") and not f.endswith(".toml"):
                continue
            with open(fp, "r") as cf:
                contents = cf.read()
                toml_dict = tomlkit.loads(contents)
                # convert tomlkit types to Python types
                json_dict = json.loads(json.dumps(toml_dict))
                if parse_device_config(json_dict, instantiate=False):
                    configs[json_dict["name"]] = json_dict
                else:
                    print(f"DeviceConfig could not be parsed: {fp}")
    return configs


def all_device_config_parsers():
    configs = [StreamingAndroidDeviceConfig, WindowsAndroidDeviceConfig, WindowsAppDeviceConfig]
    result = {}
    for c in configs:
        result[c.name()] = c
    return result


class DeviceConfig:
    @staticmethod
    def name():
        raise NotImplementedError()

    @classmethod
    def validate(cls, data: dict, throw_on_error: bool = False) -> bool:
        """
        Check for errors in the data that describes a device.
        Error-check 'conditions' are chosen based on the fields that describe the device.
        So, all fields must have the same meaning across device types.
        """
        conditions = cls.get_validation_conditions(data)
        errors = []
        for checker, message in conditions:
            if not checker():
                errors.append(message)
                break
        if throw_on_error and errors:
            raise ValueError(f"{cls.name()} couldn't be parsed because of errors: {errors}")
        elif errors:
            print("Errors found while attempting to load device:")
            for e in errors:
                print(e)
            return False
        return True

    @classmethod
    def get_validation_conditions(cls, data: dict) -> list[list[Callable, str]]:
        conditions = [
            [lambda: type(data.get("name", None)) is str,
             "Device name missing"],
            [lambda: data.get("type", None) == cls.name(),
             "Device type invalid"],
        ]
        fields = cls.get_expected_fields()
        if "adb_serial" in fields:
            conditions.append([
                lambda: type(data.get("adb_serial", None)) is str,
                "Invalid adb_serial in config; should be an alphanumeric string or an ip address " +
                "(e.g. 127.0.0.1:5555)"
            ])
        if "screenshot_size" in fields:
            conditions.extend([
                [lambda: type(data.get("screenshot_size", None)) is list,
                 "Invalid format for screenshot_size"],
                [lambda: len(data.get("screenshot_size", None)) == 2,
                 "screenshot_size should have 2 elements"],
                [lambda: all(isinstance(i, int) for i in data["screenshot_size"]),
                 "screenshot_size should be a list of ints (e.g. '[ 1, 2 ]')"]]
            )
        if "window_crop_LTRB" in fields:
            conditions.extend([
                [lambda: type(data.get("window_crop_LTRB", None)) is list,
                 "Invalid format for window_crop_LTRB"],
                [lambda: len(data.get("window_crop_LTRB", None)) == 4,
                 "window_crop_LTRB should have 4 elements"],
                [lambda: all(isinstance(i, int) for i in data["window_crop_LTRB"]),
                 "window_crop_LTRB should be a list of ints (e.g. '[ 1, 2, 3, 4 ]')"]]
            )
        if "window_title" in fields:
            conditions.append([
                lambda: type(data.get("window_title", None)) is str,
                "Invalid window_title"
            ])
        return conditions

    @classmethod
    def get_expected_fields(cls) -> list[str]:
        raise NotImplementedError()

    @classmethod
    def save(cls, data: dict, file_path: str = None):
        cls.validate(data, throw_on_error=True)
        if not file_path:
            file_path = os.path.join(DEVICE_CONFIG_FOLDER, data["name"] + ".toml")
            with open(file_path, 'w') as f:
                tomlkit.dump(data, f)

    @classmethod
    def initialize(cls, data: dict) -> Optional[Device]:
        raise NotImplementedError()


class StreamingAndroidDeviceConfig(DeviceConfig):
    @staticmethod
    def name():
        return "StreamingAndroidDevice"

    @classmethod
    def initialize(cls, data: dict) -> Optional[Device]:
        cls.validate(data, throw_on_error=True)
        return StreamingAndroidDevice(
            data["screenshot_size"],  # resolution
            ["-s", data["adb_serial"]],  # serial
        )

    @classmethod
    def get_expected_fields(cls) -> list[str]:
        return ["name", "type", "adb_serial", "screenshot_size"]


class WindowsAndroidDeviceConfig(DeviceConfig):
    @staticmethod
    def name():
        return "WindowsAndroidDevice"

    @classmethod
    def initialize(cls, data: dict) -> Optional[Device]:
        cls.validate(data, throw_on_error=True)
        if not data["adb_serial"].isalnum():
            subprocess.run(['adb', "connect", data["adb_serial"]], check=True)

        return WindowsAndroidDevice(
            data["screenshot_size"],
            ["-s", data["adb_serial"]],
            crop_settings=data["window_crop_LTRB"],
            window_title_regexes=[data["window_title"]],
        )

    @classmethod
    def get_expected_fields(cls) -> list[str]:
        return ["name", "type", "adb_serial", "screenshot_size", "window_crop_LTRB", "window_title"]


class WindowsAppDeviceConfig(DeviceConfig):
    @staticmethod
    def name():
        return "WindowsAppDevice"

    @classmethod
    def initialize(cls, data: dict) -> Optional[Device]:
        cls.validate(data, throw_on_error=True)
        return WindowsAppDevice(target_size=data["screenshot_size"],
                                crop_settings=data["window_crop_LTRB"],
                                window_title_regexes=[data["window_title"]])

    @classmethod
    def get_expected_fields(cls) -> list[str]:
        return ["name", "type", "screenshot_size", "window_crop_LTRB", "window_title"]

