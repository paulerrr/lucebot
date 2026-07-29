import json
import os

_PATH = os.getenv(
    "LUCEBOT_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "config.json"),
)
_data = {}


def load():
    global _data
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    if not os.path.exists(_PATH):
        with open(_PATH, "w") as f:
            json.dump({}, f)
        _data = {}
        return
    with open(_PATH) as f:
        _data = json.load(f)


def get(key, default=None):
    return _data.get(key, default)


def set(key, value):
    _data[key] = value
    with open(_PATH, "w") as f:
        json.dump(_data, f, indent=2)


def get_user(user_id, key, default=None):
    return _data.get("users", {}).get(str(user_id), {}).get(key, default)


def set_user(user_id, key, value):
    _data.setdefault("users", {}).setdefault(str(user_id), {})[key] = value
    with open(_PATH, "w") as f:
        json.dump(_data, f, indent=2)
