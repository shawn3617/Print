"""
Модуль гарантированного управления состоянием среды AutoCAD (AutoCADStateGuard).

Обеспечивает контекстный менеджер для защиты и восстановления параметров AutoCAD при пакетных
операциях (печать листов, сканирование чертежей, экспорт данных):
1. Сохранение и восстановление критических системных переменных:
   BACKGROUNDPLOT, FILEDIA, CMDDIA, NOMUTT, HIGHLIGHT.
2. Переключение BACKGROUNDPLOT в синхронный режим (0) на время операции.
3. Очистка временных именованных видов (_SHT_PLOT_VIEW_), созданных при печати.
4. Восстановление исходного активного листа (ActiveLayout) и активного чертежа (ActiveDocument).
5. Снятие графической подсветки объектов (clear_highlight).
6. Полная устойчивость к сбоям COM-объектов при закрытии чертежей пользователем или падениях.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from core.logger import log_info, log_warn

try:
    from core.autocad_connector import _retry_busy
except ImportError:
    def _retry_busy(func, *args, **kwargs):
        return func()


class AutoCADStateGuard:
    """
    Контекстный менеджер для гарантированного восстановления окружения AutoCAD.
    """

    SYSTEM_VARS_TO_PROTECT: Tuple[str, ...] = (
        "BACKGROUNDPLOT",
        "FILEDIA",
        "CMDDIA",
        "NOMUTT",
        "HIGHLIGHT",
    )

    def __init__(
        self,
        connector: Optional[Any] = None,
        doc: Optional[Any] = None,
        target_bg_plot: Optional[int] = 0,
    ) -> None:
        """
        Инициализация защитника состояния AutoCAD.

        :param connector: Экземпляр AutoCADConnector (если есть).
        :param doc: Объект активного чертежа AutoCAD (COM AcadDocument).
        :param target_bg_plot: Целевое значение BACKGROUNDPLOT на время работы
                               (по умолчанию 0 — синхронная печать).
                               Если None — системная переменная не изменяется.
        """
        self.connector = connector
        self.doc = doc
        self.target_bg_plot = target_bg_plot

        self.initial_active_doc: Optional[Any] = None
        self.initial_layout_name: Optional[str] = None
        self.saved_vars: Dict[str, Any] = {}
        self.touched_docs: List[Any] = []
        self._is_active: bool = False

    def _is_alive(self, com_obj: Any) -> bool:
        """
        Безопасно проверяет, жив ли COM-объект AutoCAD (не None, не закрыт и отвечает на свойство Name).
        """
        if com_obj is None:
            return False
        try:
            name = getattr(com_obj, "Name", None)
            return name is not None
        except Exception:
            return False

    def _get_effective_doc(self) -> Optional[Any]:
        """
        Возвращает доступный живой документ AutoCAD для вызова GetVariable / SetVariable.
        Проверяет doc, connector.doc, connector.app.ActiveDocument, initial_active_doc, touched_docs.
        """
        if self._is_alive(self.doc):
            return self.doc

        if self.connector:
            conn_doc = getattr(self.connector, "doc", None)
            if self._is_alive(conn_doc):
                return conn_doc
            try:
                app = getattr(self.connector, "app", None)
                if app:
                    app_doc = getattr(app, "ActiveDocument", None)
                    if self._is_alive(app_doc):
                        return app_doc
            except Exception:
                pass

        if self._is_alive(self.initial_active_doc):
            return self.initial_active_doc

        for d in self.touched_docs:
            if self._is_alive(d):
                return d

        return None

    def get_sysvar(self, name: str) -> Optional[Any]:
        """
        Считывает значение системной переменной AutoCAD через активный документ.
        Возвращает значение или None, если прочитать не удалось.
        """
        doc = self._get_effective_doc()
        if not doc:
            log_warn(f"Не удалось прочитать системную переменную {name}: нет доступного чертежа", module="AutoCADState")
            return None
        try:
            return _retry_busy(lambda: doc.GetVariable(name), max_attempts=5, delay=0.1)
        except Exception as e:
            log_warn(f"Ошибка при чтении системной переменной {name}", exc=e, module="AutoCADState")
            return None

    def set_sysvar(self, name: str, value: Any) -> bool:
        """
        Устанавливает значение системной переменной AutoCAD через активный документ.
        Возвращает True в случае успеха, False при ошибке.
        """
        if value is None:
            return False
        doc = self._get_effective_doc()
        if not doc:
            log_warn(f"Не удалось установить системную переменную {name}={value}: нет доступного чертежа", module="AutoCADState")
            return False
        try:
            _retry_busy(lambda: doc.SetVariable(name, value), max_attempts=5, delay=0.1)
            return True
        except Exception as e:
            log_warn(f"Ошибка при установке системной переменной {name}={value}", exc=e, module="AutoCADState")
            return False

    def register_doc(self, doc: Any) -> None:
        """
        Регистрирует документ AutoCAD в списке затронутых чертежей (touched_docs).
        Любые временные виды (_SHT_PLOT_VIEW_), созданные в нём, будут очищены при restore().
        """
        if doc is None or not self._is_alive(doc):
            return

        # Защита от дублирования одного и того же чертежа
        for existing in self.touched_docs:
            try:
                if existing == doc:
                    return
                fn1 = getattr(existing, "FullName", None)
                fn2 = getattr(doc, "FullName", None)
                if fn1 and fn2 and str(fn1).lower() == str(fn2).lower():
                    return
            except Exception:
                pass

        self.touched_docs.append(doc)

        # Если контекст уже активен, но переменные не были прочитаны из-за отсутствия
        # открытых чертежей на старте, читаем и инициализируем сейчас
        if self._is_active and not self.saved_vars:
            self._save_system_variables()
            if self.target_bg_plot is not None and "BACKGROUNDPLOT" in self.saved_vars:
                self.set_sysvar("BACKGROUNDPLOT", self.target_bg_plot)

    def _save_system_variables(self) -> None:
        """
        Считывает и сохраняет текущие значения SYSTEM_VARS_TO_PROTECT в saved_vars.
        """
        for var_name in self.SYSTEM_VARS_TO_PROTECT:
            val = self.get_sysvar(var_name)
            if val is not None:
                self.saved_vars[var_name] = val

    def __enter__(self) -> "AutoCADStateGuard":
        """
        Активирует защиту состояния AutoCAD:
        1. Безопасно проверяет наличие живого чертежа (doc или connector.doc).
        2. Запоминает initial_active_doc и регистрирует его в touched_docs.
        3. Запоминает initial_layout_name (имя активного листа).
        4. Читает и сохраняет системные переменные SYSTEM_VARS_TO_PROTECT.
        5. Переключает BACKGROUNDPLOT в target_bg_plot (если задан).
        6. Возвращает self.
        """
        # 1. Поиск живого чертежа
        active_doc = None
        if self._is_alive(self.doc):
            active_doc = self.doc
        elif self.connector:
            conn_doc = getattr(self.connector, "doc", None)
            if self._is_alive(conn_doc):
                active_doc = conn_doc
            else:
                try:
                    app = getattr(self.connector, "app", None)
                    if app:
                        app_doc = getattr(app, "ActiveDocument", None)
                        if self._is_alive(app_doc):
                            active_doc = app_doc
                except Exception:
                    pass

        self.initial_active_doc = active_doc
        if self.doc is None and active_doc is not None:
            self.doc = active_doc

        # 2. Регистрируем исходный чертеж
        if active_doc is not None:
            self.register_doc(active_doc)

            # 3. Запоминаем текущий лист (ActiveLayout)
            try:
                active_layout = getattr(active_doc, "ActiveLayout", None)
                if active_layout and hasattr(active_layout, "Name"):
                    self.initial_layout_name = active_layout.Name
            except Exception as e:
                log_warn("Не удалось прочитать имя исходного ActiveLayout", exc=e, module="AutoCADState")

        # 4. Сохраняем системные переменные
        self._save_system_variables()

        # 5. Устанавливаем целевой BACKGROUNDPLOT
        if self.target_bg_plot is not None:
            self.set_sysvar("BACKGROUNDPLOT", self.target_bg_plot)

        self._is_active = True
        log_info(
            f"AutoCADStateGuard активирован (сохранено переменных: {len(self.saved_vars)}, "
            f"исходный чертеж: {getattr(self.initial_active_doc, 'Name', 'нет')})",
            module="AutoCADState",
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """
        Выход из контекстного менеджера:
        Восстанавливает состояние AutoCAD и возвращает False (исключения не подавляются).
        """
        try:
            self.restore()
        except Exception as e:
            log_warn("Непредвиденная ошибка при восстановлении состояния AutoCAD", exc=e, module="AutoCADState")
        finally:
            self._is_active = False
        return False

    def restore(self) -> None:
        """
        Гарантированно восстанавливает состояние среды AutoCAD:
        1. Восстанавливает сохраненные значения системных переменных (saved_vars).
        2. Удаляет временные виды (_SHT_PLOT_VIEW_) во всех затронутых чертежах (touched_docs).
        3. Восстанавливает исходный лист (ActiveLayout) в исходном чертеже.
        4. Восстанавливает исходный активный чертеж через connector.activate_document().
        5. Снимает подсветку объектов через connector.clear_highlight().
        Устойчив к закрытым или недоступным COM-объектам на каждом шаге.
        """
        # 1. Восстановление системных переменных
        for var_name, val in list(self.saved_vars.items()):
            if val is not None:
                try:
                    self.set_sysvar(var_name, val)
                except Exception as e:
                    log_warn(f"Не удалось восстановить переменную {var_name}={val}", exc=e, module="AutoCADState")

        # 2. Очистка временных именованных видов печати во всех затронутых чертежах
        for d in list(self.touched_docs):
            if not self._is_alive(d):
                continue
            try:
                views = getattr(d, "Views", None)
                if not views:
                    continue
                views_list = []
                try:
                    views_list = list(views)
                except Exception:
                    try:
                        count = getattr(views, "Count", 0)
                        for idx in range(count):
                            views_list.append(views.Item(idx))
                    except Exception:
                        pass

                for v in views_list:
                    try:
                        v_name = getattr(v, "Name", "")
                        if v_name.startswith("_SHT_PLOT_VIEW_") or v_name == "_SHT_PLOT_VIEW":
                            v.Delete()
                    except Exception as e:
                        log_warn(f"Не удалось удалить временный вид {getattr(v, 'Name', '?')}", exc=e, module="AutoCADState")
            except Exception as e:
                log_warn("Ошибка при очистке временных видов документа", exc=e, module="AutoCADState")

        # 3. Восстановление исходного листа (ActiveLayout)
        if self.initial_layout_name and self._is_alive(self.initial_active_doc):
            try:
                cur_layout = getattr(self.initial_active_doc, "ActiveLayout", None)
                if getattr(cur_layout, "Name", None) != self.initial_layout_name:
                    try:
                        self.initial_active_doc.ActiveLayout = self.initial_active_doc.Layouts.Item(self.initial_layout_name)
                    except Exception:
                        if self.initial_layout_name.lower() == "model":
                            self.initial_active_doc.ActiveLayout = self.initial_active_doc.ModelSpace.Layout
                        else:
                            raise
            except Exception as e:
                log_warn(f"Не удалось восстановить исходный лист '{self.initial_layout_name}'", exc=e, module="AutoCADState")

        # 4. Восстановление исходного активного чертежа
        if self.initial_active_doc and self._is_alive(self.initial_active_doc):
            if self.connector and hasattr(self.connector, "activate_document"):
                try:
                    self.connector.activate_document(self.initial_active_doc)
                except Exception as e:
                    log_warn("Не удалось восстановить исходный активный чертеж через connector", exc=e, module="AutoCADState")
            elif self.connector and getattr(self.connector, "app", None):
                try:
                    self.connector.app.ActiveDocument = self.initial_active_doc
                except Exception as e:
                    log_warn("Не удалось восстановить исходный ActiveDocument", exc=e, module="AutoCADState")

            # Дополнительная проверка на случай, если смена ActiveLayout требовала активного окна
            if self.initial_layout_name:
                try:
                    cur_layout = getattr(self.initial_active_doc, "ActiveLayout", None)
                    if getattr(cur_layout, "Name", None) != self.initial_layout_name:
                        self.initial_active_doc.ActiveLayout = self.initial_active_doc.Layouts.Item(self.initial_layout_name)
                except Exception:
                    pass

        # 5. Снятие подсветки объектов
        if self.connector and hasattr(self.connector, "clear_highlight"):
            try:
                self.connector.clear_highlight()
            except Exception as e:
                log_warn("Не удалось снять подсветку объектов", exc=e, module="AutoCADState")

        log_info("AutoCADStateGuard: состояние AutoCAD успешно восстановлено", module="AutoCADState")
