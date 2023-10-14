import io
import json
import os
import datetime
from typing import Union, Any

class JSONFile:
    @staticmethod
    def save_json(filename, data):
        # type: (str, Union[dict, list]) -> None
        with io.open(filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2))

    @staticmethod
    def read_json(filename):
        # type: (str) -> Union[dict, list]
        try:
            with open(filename) as data_file:
                data = json.load(data_file)
            return data
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}


class PersistentStats:
    def __init__(self, save_name):
        # type: (str) -> PersistentStats
        self.stats = JSONFile.read_json(save_name)
        self.save_name = save_name
        JSONFile.save_json(self.save_name, self.stats)

    def increment(self, stat):
        # type: (str) -> None
        self.stats[stat] = 1 + self.stats.get(stat, 0)
        JSONFile.save_json(self.save_name, self.stats)

    def record_date(self, stat):
        # type: (str) -> None
        # This code formats the current date and time in the following format:
        # `dd-mm-yyyy (hh:mm:ss.sss)`
        self.stats[stat] = datetime.datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)")
        JSONFile.save_json(self.save_name, self.stats)

    def record_value(self, stat, value):
        # type: (str, Any) -> None
        self.stats[stat] = value
        JSONFile.save_json(self.save_name, self.stats)

    def get_value(self, stat, default):
        # type: (str, Any) -> Any
        return self.stats.get(stat, default)

    def get_dict(self):
        # type: () -> dict
        return self.stats
