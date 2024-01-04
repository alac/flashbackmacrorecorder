import tomlkit
from fbmr.devices import (
    StreamingAndroidDeviceConfig,
    WindowsAndroidDeviceConfig,
    WindowsAppDeviceConfig,
    all_device_config_parsers,
)


def base_test_config_load(class_type, input_dict, input_string):
    assert class_type.validate(input_dict)
    str_example = tomlkit.dumps(input_dict)
    example_rehydrated = tomlkit.loads(str_example)
    print(str_example)
    assert str_example == input_string
    assert example_rehydrated == input_dict

    for k in input_dict.keys():
        broken = input_dict.copy()
        del broken[k]
        assert not class_type.validate(broken)

    broken = input_dict.copy()
    broken["screenshot_size"] = [720]
    assert not class_type.validate(broken)
    broken["screenshot_size"] = [720, 1, 2]
    assert not class_type.validate(broken)
    broken["screenshot_size"] = [720, "2"]
    assert not class_type.validate(broken)


def test_scrcpy_config_load():
    input_dict = {
        "name": "s10_h",
        "type": "StreamingAndroidDevice",
        "screenshot_size": [720, 480],
        "adb_serial": "AGSDKJDF",
    }
    input_string = """name = "s10_h"
type = "StreamingAndroidDevice"
screenshot_size = [720, 480]
adb_serial = "AGSDKJDF"
"""
    class_type = StreamingAndroidDeviceConfig
    base_test_config_load(class_type, input_dict, input_string)


def test_windowsandroid_config_load():
    input_dict = {
        "name": "s10h_window",
        "type": "WindowsAndroidDevice",
        "screenshot_size": [720, 350],
        "adb_serial": "ASDFGH",
        "window_crop_LTRB": [0, 0, 0, 0],
        "window_title": "KLJ",
    }
    input_string = """name = "s10h_window"
type = "WindowsAndroidDevice"
screenshot_size = [720, 350]
adb_serial = "ASDFGH"
window_crop_LTRB = [0, 0, 0, 0]
window_title = "KLJ"
"""
    class_type = WindowsAndroidDeviceConfig
    base_test_config_load(class_type, input_dict, input_string)


def test_windowsapp_config_load():
    input_dict = {
        "name": "s10h_window",
        "type": "WindowsAppDevice",
        "screenshot_size": [720, 350],
        "window_crop_LTRB": [0, 0, 0, 0],
        "window_title": "KLJ",
    }
    input_string = """name = "s10h_window"
type = "WindowsAppDevice"
screenshot_size = [720, 350]
window_crop_LTRB = [0, 0, 0, 0]
window_title = "KLJ"
"""
    class_type = WindowsAppDeviceConfig
    base_test_config_load(class_type, input_dict, input_string)
