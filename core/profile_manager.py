"""
Менеджер профилей проектов (Project Profile Manager) для AutoCAD Batch PDF Plotter.

Позволяет сохранять, загружать, переименовывать, удалять, экспортировать
и импортировать именованные профили настроек пакетной печати и сканирования.
"""

import copy
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from core.config_manager import ConfigManager

DEFAULT_PROFILE_NAME: str = "По умолчанию"

PROFILE_KEYS: List[str] = [
    "printer",
    "plot_style",
    "fallback_paper",
    "fallback_paper_canonical",
    "merge_mode",
    "filename_template",
    "open_after_print",
    "sync_autocad",
    "source_mode",
    "frame_type",
    "custom_block_name",
]

BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "По умолчанию": {
        "printer": "DWG To PDF.pc3",
        "plot_style": "monochrome.ctb",
        "fallback_paper": "",
        "fallback_paper_canonical": "",
        "merge_mode": "В один файл (PDF)",
        "filename_template": "Лист {Номер} - {Наименование}",
        "open_after_print": True,
        "sync_autocad": True,
        "source_mode": "Модель (Model Space)",
        "frame_type": "spds",
        "custom_block_name": "",
    },
    "СПДС — В один том": {
        "printer": "DWG To PDF.pc3",
        "plot_style": "monochrome.ctb",
        "fallback_paper": "",
        "fallback_paper_canonical": "",
        "merge_mode": "В один файл (PDF)",
        "filename_template": "{Шифр}_Лист {Номер}",
        "open_after_print": True,
        "sync_autocad": True,
        "source_mode": "Модель (Model Space)",
        "frame_type": "spds",
        "custom_block_name": "",
    },
    "Отдельные листы (Шифр_Номер_Имя)": {
        "printer": "DWG To PDF.pc3",
        "plot_style": "monochrome.ctb",
        "fallback_paper": "",
        "fallback_paper_canonical": "",
        "merge_mode": "В отдельные файлы",
        "filename_template": "{Шифр}_{Номер}_{Наименование}",
        "open_after_print": True,
        "sync_autocad": True,
        "source_mode": "Модель (Model Space)",
        "frame_type": "spds",
        "custom_block_name": "",
    },
    "Пространство Листов (Layouts)": {
        "printer": "DWG To PDF.pc3",
        "plot_style": "monochrome.ctb",
        "fallback_paper": "",
        "fallback_paper_canonical": "",
        "merge_mode": "В один файл (PDF)",
        "filename_template": "Лист {Номер} - {Наименование}",
        "open_after_print": True,
        "sync_autocad": True,
        "source_mode": "Листы (Layouts)",
        "frame_type": "all_blocks",
        "custom_block_name": "",
    },
}


class ProfileManager:
    """Управление профилями настроек приложения."""

    DEFAULT_PROFILE_NAME: str = DEFAULT_PROFILE_NAME
    BUILTIN_PROFILES: Dict[str, Dict[str, Any]] = BUILTIN_PROFILES
    PROFILE_KEYS: List[str] = PROFILE_KEYS

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Инициализирует менеджер профилей.
        Если config_manager не передан, создает стандартный экземпляр ConfigManager.
        Считывает сохраненные профили из конфигурации.
        """
        if config_manager is None:
            self.config_manager = ConfigManager()
        else:
            self.config_manager = config_manager

        cfg = self.config_manager.load()
        if not isinstance(cfg, dict):
            cfg = {}

        raw_profiles = cfg.get("profiles", {})
        if not raw_profiles and isinstance(self.config_manager.get("profiles"), dict):
            raw_profiles = self.config_manager.get("profiles")

        self.profiles: Dict[str, Dict[str, Any]] = dict(raw_profiles) if isinstance(raw_profiles, dict) else {}

    def is_builtin(self, name: str) -> bool:
        """Возвращает True, если профиль является встроенным."""
        return name in self.BUILTIN_PROFILES

    def get_profile_names(self) -> List[str]:
        """
        Возвращает список имен профилей.
        Всегда начинается со встроенных (в фиксированном порядке),
        затем пользовательские профили в алфавитном порядке.
        """
        builtin_names = list(self.BUILTIN_PROFILES.keys())
        user_names = sorted([name for name in self.profiles.keys() if name not in self.BUILTIN_PROFILES])
        return builtin_names + user_names

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает копию словаря настроек для профиля `name` (или None, если не найден).
        Объединяет со значениями по умолчанию для любых отсутствующих ключей.
        """
        if not name or not isinstance(name, str):
            return None

        name = name.strip()
        if name not in self.BUILTIN_PROFILES and name not in self.profiles:
            return None

        # Базовый набор берем из встроенного профиля (если есть) или из "По умолчанию"
        if name in self.BUILTIN_PROFILES:
            base = copy.deepcopy(self.BUILTIN_PROFILES[name])
        else:
            base = copy.deepcopy(self.BUILTIN_PROFILES[self.DEFAULT_PROFILE_NAME])

        # Если есть пользовательские настройки для этого профиля, накладываем их
        if name in self.profiles and isinstance(self.profiles[name], dict):
            for k in self.PROFILE_KEYS:
                if k in self.profiles[name]:
                    base[k] = copy.deepcopy(self.profiles[name][k])

        return base

    def get_active_profile_name(self) -> str:
        """
        Возвращает имя активного профиля из конфига (по умолчанию 'По умолчанию').
        """
        active = self.config_manager.get("active_profile", self.DEFAULT_PROFILE_NAME)
        if not active or not isinstance(active, str):
            return self.DEFAULT_PROFILE_NAME
        active = active.strip()
        if active not in self.get_profile_names():
            return self.DEFAULT_PROFILE_NAME
        return active

    def set_active_profile_name(self, name: str) -> bool:
        """
        Устанавливает имя активного профиля и сохраняет конфигурацию.
        """
        if not name or not isinstance(name, str):
            return False
        name = name.strip()
        if name not in self.get_profile_names():
            return False
        return self.config_manager.save({"active_profile": name})

    def extract_profile_settings(self, full_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлекает и возвращает словарь, содержащий только ключи из PROFILE_KEYS.
        """
        if not isinstance(full_dict, dict):
            return {}
        return {k: full_dict[k] for k in self.PROFILE_KEYS if k in full_dict}

    def save_profile(self, name: str, settings: Dict[str, Any]) -> bool:
        """
        Сохраняет настройки профиля под именем `name`.
        Фильтрует `settings` только по `PROFILE_KEYS`.
        Не позволяет перезаписать 'По умолчанию' пустым словарем,
        но позволяет обновлять пользовательские переопределения встроенных
        или кастомных профилей.
        Сохраняет в config_manager под ключом 'profiles'.
        Возвращает True при успешном сохранении.
        """
        if not name or not isinstance(name, str):
            return False
        name = name.strip()
        if not name:
            return False

        filtered = self.extract_profile_settings(settings)
        if name == self.DEFAULT_PROFILE_NAME and not filtered:
            return False

        # Формируем полный словарь настроек
        if name in self.BUILTIN_PROFILES:
            base = copy.deepcopy(self.BUILTIN_PROFILES[name])
        else:
            base = copy.deepcopy(self.BUILTIN_PROFILES[self.DEFAULT_PROFILE_NAME])

        if name in self.profiles and isinstance(self.profiles[name], dict):
            base.update(self.profiles[name])

        base.update(filtered)
        self.profiles[name] = base

        return self.config_manager.save({"profiles": self.profiles})

    def create_profile(self, name: str, settings: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Создает новый профиль.
        Проверяет имя на непустоту и отсутствие дубликатов.
        Если имя уже существует, возвращает (False, f"Профиль «{name}» уже существует").
        Возвращает (True, "") при успехе.
        """
        if not name or not isinstance(name, str):
            return (False, "Имя профиля не может быть пустым")

        name = name.strip()
        if not name:
            return (False, "Имя профиля не может быть пустым")

        if name in self.get_profile_names():
            return (False, f"Профиль «{name}» уже существует")

        if not self.save_profile(name, settings):
            return (False, "Ошибка при сохранении профиля")

        return (True, "")

    def rename_profile(self, old_name: str, new_name: str) -> Tuple[bool, str]:
        """
        Переименовывает профиль `old_name` в `new_name`.
        Нельзя переименовать 'По умолчанию' -> (False, "Нельзя переименовать базовый профиль «По умолчанию»").
        Проверяет, что `new_name` валидно и не занято.
        Обновляет словарь профилей, обновляет активный профиль (если он был old_name), сохраняет конфиг.
        Возвращает (True, "") при успехе.
        """
        if not old_name or not isinstance(old_name, str):
            return (False, "Имя профиля не может быть пустым")

        old_name = old_name.strip()
        if old_name == self.DEFAULT_PROFILE_NAME:
            return (False, "Нельзя переименовать базовый профиль «По умолчанию»")

        if old_name not in self.get_profile_names():
            return (False, f"Профиль «{old_name}» не найден")

        if not new_name or not isinstance(new_name, str):
            return (False, "Новое имя профиля не может быть пустым")

        new_name = new_name.strip()
        if not new_name:
            return (False, "Новое имя профиля не может быть пустым")

        if new_name == old_name:
            return (True, "")

        if new_name in self.get_profile_names():
            return (False, f"Профиль «{new_name}» уже существует")

        was_active = (self.get_active_profile_name() == old_name)

        current_settings = self.get_profile(old_name)
        if current_settings is None:
            return (False, f"Не удалось получить настройки профиля «{old_name}»")

        self.profiles[new_name] = current_settings
        if old_name in self.profiles:
            del self.profiles[old_name]

        save_data: Dict[str, Any] = {"profiles": self.profiles}
        if was_active:
            save_data["active_profile"] = new_name

        if not self.config_manager.save(save_data):
            return (False, "Ошибка при сохранении конфигурации после переименования")

        return (True, "")

    def delete_profile(self, name: str) -> Tuple[bool, str]:
        """
        Удаляет профиль `name`.
        Нельзя удалить 'По умолчанию' -> (False, "Нельзя удалить базовый профиль «По умолчанию»").
        Удаляет из пользовательских профилей в конфиге.
        Если активный профиль был удален, переключает активный на 'По умолчанию'. Сохраняет конфиг.
        Возвращает (True, "") при успехе.
        """
        if not name or not isinstance(name, str):
            return (False, "Имя профиля не может быть пустым")

        name = name.strip()
        if name == self.DEFAULT_PROFILE_NAME:
            return (False, "Нельзя удалить базовый профиль «По умолчанию»")

        if name not in self.get_profile_names():
            return (False, f"Профиль «{name}» не найден")

        was_active = (self.get_active_profile_name() == name)

        if name in self.profiles:
            del self.profiles[name]

        save_data: Dict[str, Any] = {"profiles": self.profiles}
        if was_active:
            save_data["active_profile"] = self.DEFAULT_PROFILE_NAME

        if not self.config_manager.save(save_data):
            return (False, "Ошибка при сохранении конфигурации после удаления")

        return (True, "")

    def export_profile(self, name: str, filepath: str) -> Tuple[bool, str]:
        """
        Экспортирует словарь настроек профиля в виде форматированного JSON-файла
        с метаданными: {"profile_name": name, "settings": ...}.
        Возвращает (True, "") или (False, error_message).
        """
        if not name or not isinstance(name, str):
            return (False, "Имя профиля не может быть пустым")

        name = name.strip()
        settings = self.get_profile(name)
        if settings is None:
            return (False, f"Профиль «{name}» не найден")

        payload = {
            "profile_name": name,
            "settings": settings,
        }

        try:
            dir_name = os.path.dirname(os.path.abspath(filepath))
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return (True, "")
        except Exception as e:
            return (False, f"Ошибка при экспорте профиля «{name}»: {e}")

    def import_profile(self, filepath: str) -> Tuple[bool, str, Optional[str]]:
        """
        Читает JSON-файл, валидирует формат, извлекает имя профиля и настройки.
        Если профиль с таким именем уже существует, генерирует уникальное имя
        вида f"{name} (импорт)".
        Сохраняет новый профиль и возвращает (True, "", new_profile_name).
        При ошибке возвращает (False, error_message, None).
        """
        if not filepath or not os.path.isfile(filepath):
            return (False, f"Файл не найден: «{filepath}»", None)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return (False, f"Ошибка чтения JSON-файла: {e}", None)

        if not isinstance(data, dict):
            return (False, "Неверный формат: файл должен содержать JSON-объект", None)

        if "settings" in data and isinstance(data["settings"], dict):
            raw_settings = data["settings"]
            profile_name = data.get("profile_name")
        else:
            raw_settings = data
            profile_name = None

        if not profile_name or not isinstance(profile_name, str) or not profile_name.strip():
            profile_name = os.path.splitext(os.path.basename(filepath))[0]

        profile_name = profile_name.strip()
        filtered = self.extract_profile_settings(raw_settings)
        if not filtered:
            return (False, "Файл не содержит допустимых настроек профиля", None)

        # Подбираем уникальное имя при наличии конфликта
        existing_names = set(self.get_profile_names())
        target_name = profile_name
        if target_name in existing_names:
            candidate = f"{target_name} (импорт)"
            if candidate not in existing_names:
                target_name = candidate
            else:
                idx = 2
                while f"{target_name} (импорт {idx})" in existing_names:
                    idx += 1
                target_name = f"{target_name} (импорт {idx})"

        if not self.save_profile(target_name, filtered):
            return (False, f"Не удалось сохранить профиль «{target_name}»", None)

        return (True, "", target_name)

    def apply_profile_to_config(self, name: str) -> bool:
        """
        Применяет настройки профиля `name` к конфигурации приложения (config_manager)
        и делает данный профиль активным.
        """
        settings = self.get_profile(name)
        if settings is None:
            return False
        update_data = dict(settings)
        update_data["active_profile"] = name
        return self.config_manager.save(update_data)
