import os
import pyjson5
import shutil
from pathlib import Path
import pytest

from fbmr.conditions import SubimageCondition
from fbmr.config import Config, Action
from fbmr.effects import ClickSubimageEffect

TESTDATA_COND = "tests/test_data_conditions/"
TESTDATA_CONFIG = "tests/test_data_config/"


@pytest.fixture
def setup_and_teardown():
    """Setup and teardown code."""
    nuke_test_folder()
    yield
    nuke_test_folder()


def nuke_test_folder():
    if os.path.exists(TESTDATA_CONFIG):
        shutil.rmtree(TESTDATA_CONFIG)
    Path(TESTDATA_CONFIG).mkdir(parents=True, exist_ok=True)


def test_create(setup_and_teardown):
    config = Config(TESTDATA_CONFIG, "test1", create_if_missing=True)
    action = Action("empty", [], [], True, [], 0, None, TESTDATA_CONFIG + "test2")
    config.add_action(action)
    assert config.make_json() == {
        "name": "test1",
        "actions": [
            {
                "name": "empty",
                "cooldown": 0,
                "conditions": [],
                "effects": [],
                "is_enabled": True,
                "next_action_names": [],
            }
        ],
        "confirmAll": False,
        "screenshot_size": None,
    }

    # Read
    config2 = Config(TESTDATA_CONFIG, "test1")
    assert config2.make_json() == config.make_json()


def test_create2(setup_and_teardown):
    config = Config(TESTDATA_CONFIG, "test2", create_if_missing=True)
    condition = SubimageCondition(
        TESTDATA_COND + "button.png",
        (603, 914, 603 + 503, 914 + 346),
        80,
        1.0,
        "button",
    )
    effect = ClickSubimageEffect(
        TESTDATA_COND + "button.png", (603, 914, 603 + 503, 914 + 346), [1, 2]
    )

    action = Action(
        "action1", [condition], [effect], True, [], 0, None, TESTDATA_CONFIG + "test2"
    )
    config.add_action(action)
    assert config.make_json() == {
        "name": "test2",
        "actions": [
            {
                "name": "action1",
                "conditions": [
                    {
                        "type": "SubimageCondition",
                        "image_path": f"{TESTDATA_COND}button.png",
                        "intended_region": (603, 914, 1106, 1260),
                        "threshold": 80,
                        "weight": 1.0,
                        "save_region_as": "button",
                    }
                ],
                "cooldown": 0,
                "effects": [
                    {
                        "type": "ClickSubimageEffect",
                        "image_path": f"{TESTDATA_COND}button.png",
                        "intended_region": (603, 914, 1106, 1260),
                        "tap_coords_in_image": [1, 2],
                    }
                ],
                "is_enabled": True,
                "next_action_names": [],
            },
        ],
        "screenshot_size": None,
        "confirmAll": False,
    }

    # Read
    config2 = Config(TESTDATA_CONFIG, "test2")
    assert pyjson5.dumps(config2.make_json()) == pyjson5.dumps(config.make_json())

    # Add 2nd action
    action = Action(
        "action2", [condition], [effect], True, [], 0, None, TESTDATA_CONFIG + "test2"
    )
    config.add_action(action)

    # Read
    config2 = Config(TESTDATA_CONFIG, "test2")
    assert len(config2.make_json()["actions"]) == 2
    action_names = sorted([aj["name"] for aj in config2.make_json()["actions"]])
    assert action_names == ["action1", "action2"]
