import json
import os
from astrbot.api import logger

BINDINGS_FILE = os.path.join(os.path.dirname(__file__), "bindings.json")


def _load() -> dict[str, dict]:
    if not os.path.exists(BINDINGS_FILE):
        return {}
    try:
        with open(BINDINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"读取绑定数据失败: {e}")
        return {}


def _save(data: dict[str, dict]):
    try:
        with open(BINDINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存绑定数据失败: {e}")


def bind(user_id: str, profile_id: int, player_name: str) -> bool:
    data = _load()
    data[user_id] = {"profile_id": profile_id, "player_name": player_name}
    _save(data)
    logger.info(f"用户 {user_id} 绑定 {player_name}({profile_id})")
    return True


def unbind(user_id: str) -> bool:
    data = _load()
    if user_id in data:
        del data[user_id]
        _save(data)
        logger.info(f"用户 {user_id} 解绑")
        return True
    return False


def get_bound(user_id: str) -> dict | None:
    data = _load()
    return data.get(user_id)
