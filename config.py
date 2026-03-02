import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_data = {}


def load():
    global _data
    if os.path.exists(_PATH):
        with open(_PATH) as f:
            _data = json.load(f)


def get(key, default=None):
    return _data.get(key, default)


def set(key, value):
    _data[key] = value
    with open(_PATH, "w") as f:
        json.dump(_data, f, indent=2)
