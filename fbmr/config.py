import json
import os
import pyjson5
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from fbmr.conditions import load_condition, Condition
from fbmr.effects import load_effect, Effect
from fbmr.utils.debug_settings import debug_settings


class Config:
    """
    The Config class is the datastore for a visual macro. Conceptually, it's a big blob of Action objects, each of which
    represents a set of Conditions to trigger the Action and a set of Effects. When an Action completes, it can lead
    the execution of other Actions. A sequence of Actions that lead to other actions is called an 'action chain'.
    A single config can consist of a single action chain, or many unrelated actions/action chains.

    On disk, a Config is represented by a folder containing a 'config.json' and whatever images it might use.
    """
    def __init__(self, configs_root, name, create_if_missing=False):
        # type: (str, str, bool) -> None
        self.name = name
        self.actions = []
        self.actionsMap = {}
        self.confirmAll = False
        self.screenshot_size = None  # type: Optional[Tuple[int, int]]
        self.autosave = True

        self.folder_path = os.path.join(configs_root, name)
        self.json_path = os.path.join(configs_root, name, "config.json")

        if not create_if_missing:
            if not os.path.exists(self.folder_path):
                raise ValueError(f"Attempted to load a config that does not exist! {self.folder_path}")

        # if the folder or json don't exist, create them
        assert os.path.isdir(configs_root)
        Path(self.folder_path).mkdir(parents=True, exist_ok=True)

        # if they do exist, read from them
        if os.path.exists(self.json_path):
            self.read()
        else:
            self.write()

    def read(self):
        # type: () -> None
        with open(self.json_path) as json_file:
            data = pyjson5.load(json_file)
            self.load_json(data)

    def write(self):
        # type: () -> None
        data = self.make_json()
        with open(self.json_path, 'w') as outfile:
            json.dump(data, outfile, ensure_ascii=False, sort_keys=True, indent=2)

    def load_json(self, json_blob):
        # type: (dict) -> None
        self.confirmAll = json_blob.get('confirmAll', False)
        self.screenshot_size = json_blob.get('screenshot_size', False)
        self.actions = []
        for action_json in json_blob['actions']:
            name = action_json["name"]
            action = Action.load(action_json, self.folder_path)
            if name in self.actionsMap:
                raise ValueError(f"Name collision for {name}")
            self.actionsMap[name] = action
            self.actions.append(action)

    def make_json(self):
        # type: () -> dict
        d = {'name': self.name, 'actions': [a.make_json() for a in self.actions], 'confirmAll': self.confirmAll,
             'screenshot_size': self.screenshot_size}
        return d

    def add_action(self, action, temp=False):
        # type: (Action, bool) -> None
        self.actions.append(action)
        self.actionsMap[action.name] = action
        if temp:
            self.autosave = False
        if self.autosave:
            self.write()

    def get_action(self, name):
        # type: (str) -> Action
        return self.actionsMap[name]


class Action(object):
    def __init__(self, name, conditions, effects, is_enabled, next_action_names, cooldown, advance_if_condition,
                 folder_path):
        # type: (str, list[Condition], list[Effect], bool, list[str], float, Optional[Condition], str) -> None
        self.name = name
        self.conditions = conditions  # condition objects
        self.effects = effects  # effect objects
        self.is_enabled = is_enabled
        self.next_action_names = next_action_names
        self.cooldown = cooldown
        self.advance_if_condition = advance_if_condition
        self.folder_path = folder_path

    def set_folder_path(self, folder_path):
        # type: (str) -> None
        self.folder_path = folder_path
        for c in self.conditions:
            c.set_folder_path(folder_path)
        for e in self.effects:
            e.set_folder_path(folder_path)

    def make_json(self):
        # type: () -> dict
        d = {'name': self.name, 'conditions': [c.make_json() for c in self.conditions],
             'effects': [e.make_json() for e in self.effects], 'is_enabled': self.is_enabled,
             'next_action_names': self.next_action_names, 'cooldown': self.cooldown}
        if self.advance_if_condition:
            d['advance_if_condition'] = self.advance_if_condition.make_json()
        return d

    @staticmethod
    def load(json_data, folder_path):
        # type: (dict, str) -> Action
        conditions = []
        for c_data in json_data['conditions']:
            conditions.append(load_condition(c_data, folder_path))

        effects = []
        for e_data in json_data['effects']:
            effects.append(load_effect(e_data, folder_path))

        adv_if_data = json_data.get('advance_if_condition', None)
        advance_if_condition = None
        if adv_if_data is not None:
            advance_if_condition = load_condition(adv_if_data, folder_path)

        return Action(
            json_data['name'],
            conditions,
            effects,
            json_data['is_enabled'],
            json_data.get('next_action_names', []),
            json_data.get('cooldown', 0),
            advance_if_condition,
            folder_path
        )

    def find_valid_rect(self, pil_image, state_dict, utils):
        # type: (Image, dict, dict) -> (float, Tuple[int, int, int, int])
        if len(self.conditions) == 0:
            return 0, (0, 0, 0, 0)

        if not self.is_enabled:
            return 0, (0, 0, 0, 0)

        debug_settings.action_logger(f"Checking action: {self.name}")
        min_validity = 100.0
        min_rect = (0, 0, 0, 0)
        for c in self.conditions:
            validity, rect = c.find_valid_rect(pil_image, state_dict, utils)
            if validity < min_validity:
                min_validity = validity
                min_rect = rect
        if len(self.conditions) > 0:
            debug_settings.action_logger(f"Action score: {int(min_validity)}")
        return min_validity, min_rect

    def is_valid(self, pil_image, state_dict, utils):
        # type: (Image, dict, dict) -> float
        validity, rect = self.find_valid_rect(pil_image, state_dict, utils)
        return validity

    def apply(self, pil_image, state_dict, utils):
        # type: (Image, dict, dict) -> None
        for e in self.effects:
            e.apply(pil_image, state_dict, utils)
