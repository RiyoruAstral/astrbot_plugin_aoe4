import os
import json

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


def _ensure_dirs():
    dirs = [
        os.path.join(_PLUGIN_DIR, "data"),
        os.path.join(_PLUGIN_DIR, "data", "i18n"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def _ensure_bindings():
    path = os.path.join(_PLUGIN_DIR, "bindings.json")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)


_ensure_dirs()
_ensure_bindings()
