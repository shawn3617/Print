import json
import os
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "printer": "DWG To PDF.pc3",
    "plot_style": "monochrome.ctb",
    "fallback_paper": "",
    "merge_mode": "В один файл (PDF)",
    "open_after_print": True,
    "sync_autocad": True,
    "source_mode": "Модель (Model Space)",
}


def get_default_config_path() -> str:
    """Возвращает путь к config.json в корне проекта."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, "config.json")


class ConfigManager:
    """Управление конфигурацией приложения (чтение и запись config.json)."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or get_default_config_path()
        self.config: Dict[str, Any] = dict(DEFAULT_CONFIG)

    def load(self) -> Dict[str, Any]:
        """Загружает настройки из файла. При отсутствии или ошибке возвращает значения по умолчанию."""
        if not os.path.exists(self.config_path):
            self.config = dict(DEFAULT_CONFIG)
            return dict(self.config)

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged = dict(DEFAULT_CONFIG)
                    merged.update(data)
                    self.config = merged
                else:
                    self.config = dict(DEFAULT_CONFIG)
        except Exception as e:
            print(f"[ConfigManager] Предупреждение: ошибка чтения {self.config_path}: {e}. Используются настройки по умолчанию.")
            self.config = dict(DEFAULT_CONFIG)

        return dict(self.config)

    def save(self, new_data: Dict[str, Any] = None) -> bool:
        """Сохраняет текущие настройки (или переданные new_data) в config.json."""
        if new_data:
            self.config.update(new_data)

        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[ConfigManager] Ошибка сохранения {self.config_path}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value
