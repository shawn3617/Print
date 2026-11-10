"""
Модульные тесты для core/autocad_state.py (AutoCADStateGuard).

Проверяет:
1. Сохранение системных переменных на входе и восстановление на выходе (нормальном и аварийном).
2. Установку переменной BACKGROUNDPLOT в target_bg_plot (0).
3. Очистку временных видов печати (_SHT_PLOT_VIEW_*) в основном и вторичных чертежах.
4. Восстановление исходного листа (ActiveLayout) и исходного активного документа.
5. Вызов connector.clear_highlight() для снятия подсветки.
6. Устойчивость к None-параметрам, мертвым COM-объектам и исключениям.
"""

from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, call, patch

from core.autocad_state import AutoCADStateGuard


# ============================================================================
# Вспомогательные классы и функции для симуляции COM-объектов AutoCAD
# ============================================================================

class DeadComObject:
    """
    Имитирует мертвый COM-объект AutoCAD (закрытый чертеж или отвалившийся процесс),
    обращение к свойствам которого вызывает ошибку COM/RPC.
    """

    @property
    def Name(self) -> str:
        raise RuntimeError("0x80010108: The object invoked has disconnected from its clients")

    @property
    def FullName(self) -> str:
        raise RuntimeError("0x80010108: The object invoked has disconnected from its clients")


class DisconnectingDoc:
    """
    Имитирует чертеж AutoCAD, который доступен на входе в контекстный менеджер,
    но принудительно «закрывается» (отключается) во время выполнения операции.
    """

    def __init__(self, name: str = "disconnecting.dwg", full_name: str = "C:/drawings/disconnecting.dwg") -> None:
        self._alive: bool = True
        self._name: str = name
        self._full_name: str = full_name
        self.Views: List[Any] = []
        self.ActiveLayout: Any = MagicMock(Name="Model")
        self.Layouts: Any = MagicMock()
        self.ModelSpace: Any = MagicMock()
        self._sysvars: Dict[str, Any] = {
            "BACKGROUNDPLOT": 2,
            "FILEDIA": 1,
            "CMDDIA": 1,
            "NOMUTT": 0,
            "HIGHLIGHT": 1,
        }

    def disconnect(self) -> None:
        """Отключает документ, симулируя закрытие COM-объекта."""
        self._alive = False

    @property
    def Name(self) -> str:
        if not self._alive:
            raise RuntimeError("RPC server is unavailable")
        return self._name

    @property
    def FullName(self) -> str:
        if not self._alive:
            raise RuntimeError("RPC server is unavailable")
        return self._full_name

    def GetVariable(self, name: str) -> Any:
        if not self._alive:
            raise RuntimeError("RPC server is unavailable")
        return self._sysvars.get(name)

    def SetVariable(self, name: str, value: Any) -> None:
        if not self._alive:
            raise RuntimeError("RPC server is unavailable")
        self._sysvars[name] = value


class MockNonIterableViews:
    """
    Имитирует COM-коллекцию AcadViews, которая не поддерживает прямое итерирование
    через Python __iter__, но поддерживает .Count и .Item(idx).
    """

    def __init__(self, items: List[Any]) -> None:
        self._items: List[Any] = items

    def __iter__(self):
        raise TypeError("'MockNonIterableViews' object is not iterable")

    @property
    def Count(self) -> int:
        return len(self._items)

    def Item(self, idx: int) -> Any:
        return self._items[idx]


def create_mock_doc(
    name: str = "drawing1.dwg",
    full_path: str = "C:/drawings/drawing1.dwg",
    initial_layout: str = "Model",
    sysvars: Optional[Dict[str, Any]] = None,
    views: Optional[List[Any]] = None,
) -> MagicMock:
    """
    Создает полноценный mock-объект чертежа AutoCAD (AcadDocument).
    """
    doc = MagicMock()
    doc.Name = name
    doc.FullName = full_path

    # Настройка вкладок / Layouts
    active_layout = MagicMock()
    active_layout.Name = initial_layout
    doc.ActiveLayout = active_layout

    model_layout = MagicMock()
    model_layout.Name = "Model"
    doc.ModelSpace.Layout = model_layout

    layout_items: Dict[str, MagicMock] = {
        initial_layout: active_layout,
        "Model": model_layout,
    }
    doc.Layouts.Item.side_effect = lambda n: layout_items.get(n, MagicMock(Name=n))

    # Настройка видов
    doc.Views = list(views) if views is not None else []

    # Настройка системных переменных
    vars_store: Dict[str, Any] = {
        "BACKGROUNDPLOT": 2,
        "FILEDIA": 1,
        "CMDDIA": 1,
        "NOMUTT": 0,
        "HIGHLIGHT": 1,
    }
    if sysvars:
        vars_store.update(sysvars)

    doc.GetVariable.side_effect = lambda var_name: vars_store.get(var_name)

    def _set_var(var_name: str, value: Any) -> None:
        vars_store[var_name] = value

    doc.SetVariable.side_effect = _set_var
    doc._vars_store = vars_store

    return doc


def create_mock_connector(doc: Optional[Any] = None) -> MagicMock:
    """
    Создает mock-объект коннектора к AutoCAD (AutoCADConnector).
    """
    connector = MagicMock()
    connector.doc = doc
    connector.app = MagicMock()
    connector.app.ActiveDocument = doc
    return connector


# ============================================================================
# 1. Тесты входа и выхода из контекстного менеджера (системные переменные)
# ============================================================================

class TestAutoCADStateGuardEnterExit(unittest.TestCase):
    """
    Тестирование сохранения и восстановления системных переменных AutoCAD при входе и выходе.
    """

    def test_enter_saves_all_protected_variables(self):
        """Проверяет, что при входе считываются и сохраняются все переменные SYSTEM_VARS_TO_PROTECT."""
        doc = create_mock_doc(sysvars={
            "BACKGROUNDPLOT": 2,
            "FILEDIA": 0,
            "CMDDIA": 1,
            "NOMUTT": 1,
            "HIGHLIGHT": 0,
        })
        guard = AutoCADStateGuard(doc=doc, target_bg_plot=0)

        with guard:
            self.assertEqual(guard.saved_vars["BACKGROUNDPLOT"], 2)
            self.assertEqual(guard.saved_vars["FILEDIA"], 0)
            self.assertEqual(guard.saved_vars["CMDDIA"], 1)
            self.assertEqual(guard.saved_vars["NOMUTT"], 1)
            self.assertEqual(guard.saved_vars["HIGHLIGHT"], 0)

    def test_enter_sets_backgroundplot_to_target(self):
        """Проверяет, что при входе BACKGROUNDPLOT переключается в target_bg_plot (по умолчанию 0)."""
        doc = create_mock_doc(sysvars={"BACKGROUNDPLOT": 2})
        guard = AutoCADStateGuard(doc=doc, target_bg_plot=0)

        self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 2)
        with guard:
            # Внутри контекста фоновая печать отключена
            self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 0)

    def test_enter_with_custom_target_bg_plot(self):
        """Проверяет установку произвольного target_bg_plot (например, 1)."""
        doc = create_mock_doc(sysvars={"BACKGROUNDPLOT": 0})
        guard = AutoCADStateGuard(doc=doc, target_bg_plot=1)

        with guard:
            self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 1)

    def test_enter_with_none_target_bg_plot_does_not_modify_backgroundplot(self):
        """Если target_bg_plot=None, значение BACKGROUNDPLOT при входе не изменяется."""
        doc = create_mock_doc(sysvars={"BACKGROUNDPLOT": 2})
        guard = AutoCADStateGuard(doc=doc, target_bg_plot=None)

        with guard:
            self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 2)
            # Убеждаемся, что doc.SetVariable("BACKGROUNDPLOT", ...) не вызывался
            calls = [c for c in doc.SetVariable.call_args_list if c[0][0] == "BACKGROUNDPLOT"]
            self.assertEqual(len(calls), 0)

    def test_normal_exit_restores_all_saved_variables(self):
        """При нормальном выходе все сохраненные системные переменные возвращаются к исходным значениям."""
        doc = create_mock_doc(sysvars={
            "BACKGROUNDPLOT": 2,
            "FILEDIA": 1,
            "CMDDIA": 1,
            "NOMUTT": 0,
            "HIGHLIGHT": 1,
        })
        guard = AutoCADStateGuard(doc=doc, target_bg_plot=0)

        with guard:
            # Изменяем переменные внутри контекста (симулируя печать)
            doc.SetVariable("FILEDIA", 0)
            doc.SetVariable("CMDDIA", 0)
            doc.SetVariable("NOMUTT", 1)
            doc.SetVariable("HIGHLIGHT", 0)

        # После выхода все должно вернуться к исходным значениям
        self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 2)
        self.assertEqual(doc._vars_store["FILEDIA"], 1)
        self.assertEqual(doc._vars_store["CMDDIA"], 1)
        self.assertEqual(doc._vars_store["NOMUTT"], 0)
        self.assertEqual(doc._vars_store["HIGHLIGHT"], 1)

    def test_exit_on_exception_restores_variables_and_reraises(self):
        """При исключении внутри with переменные гарантированно восстанавливаются, а исключение пробрасывается."""
        doc = create_mock_doc(sysvars={"BACKGROUNDPLOT": 2, "FILEDIA": 1})
        guard = AutoCADStateGuard(doc=doc, target_bg_plot=0)

        with self.assertRaises(ZeroDivisionError):
            with guard:
                self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 0)
                _ = 1 / 0

        # Переменная BACKGROUNDPLOT должна быть возвращена в исходное значение 2
        self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 2)
        self.assertEqual(doc._vars_store["FILEDIA"], 1)

    def test_enter_finds_doc_from_connector_if_doc_arg_is_none(self):
        """Если doc не передан, guard берет активный документ из connector.doc."""
        doc = create_mock_doc(name="from_conn.dwg", sysvars={"BACKGROUNDPLOT": 2})
        connector = create_mock_connector(doc=doc)

        guard = AutoCADStateGuard(connector=connector, doc=None, target_bg_plot=0)
        with guard:
            self.assertEqual(guard.initial_active_doc, doc)
            self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 0)

        self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 2)

    def test_enter_finds_doc_from_connector_app_active_document(self):
        """Если connector.doc равен None, guard берет документ из connector.app.ActiveDocument."""
        doc = create_mock_doc(name="from_app.dwg", sysvars={"BACKGROUNDPLOT": 2})
        connector = MagicMock()
        connector.doc = None
        connector.app.ActiveDocument = doc

        guard = AutoCADStateGuard(connector=connector, doc=None, target_bg_plot=0)
        with guard:
            self.assertEqual(guard.initial_active_doc, doc)
            self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 0)

        self.assertEqual(doc._vars_store["BACKGROUNDPLOT"], 2)


# ============================================================================
# 2. Тесты очистки временных видов печати (_SHT_PLOT_VIEW_*)
# ============================================================================

class TestAutoCADStateGuardViewsCleanup(unittest.TestCase):
    """
    Тестирование удаления временных видов печати (_SHT_PLOT_VIEW_*) и сохранения пользовательских видов.
    """

    def test_temporary_views_deleted_and_user_views_preserved(self):
        """
        Временные виды _SHT_PLOT_VIEW_* и _SHT_PLOT_VIEW удаляются (v.Delete()),
        а пользовательские виды остаются нетронутыми.
        """
        view_temp1 = MagicMock(Name="_SHT_PLOT_VIEW_1")
        view_temp2 = MagicMock(Name="_SHT_PLOT_VIEW_2")
        view_temp_single = MagicMock(Name="_SHT_PLOT_VIEW")
        view_user = MagicMock(Name="UserView")
        view_arch = MagicMock(Name="План_1_этажа")

        all_views = [view_temp1, view_user, view_temp2, view_arch, view_temp_single]
        doc = create_mock_doc(views=all_views)

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            pass

        # Временные виды должны быть удалены
        view_temp1.Delete.assert_called_once()
        view_temp2.Delete.assert_called_once()
        view_temp_single.Delete.assert_called_once()

        # Пользовательские виды НЕ должны быть удалены
        view_user.Delete.assert_not_called()
        view_arch.Delete.assert_not_called()

    def test_register_doc_cleans_views_in_secondary_docs(self):
        """
        Документы, зарегистрированные в процессе работы через register_doc(),
        также очищаются от временных видов при выходе.
        """
        doc1_temp_view = MagicMock(Name="_SHT_PLOT_VIEW_10")
        doc1_user_view = MagicMock(Name="Doc1_NormalView")
        doc1 = create_mock_doc(name="doc1.dwg", views=[doc1_temp_view, doc1_user_view])

        doc2_temp_view = MagicMock(Name="_SHT_PLOT_VIEW_20")
        doc2_user_view = MagicMock(Name="Doc2_NormalView")
        doc2 = create_mock_doc(name="doc2.dwg", full_path="C:/drawings/doc2.dwg", views=[doc2_temp_view, doc2_user_view])

        guard = AutoCADStateGuard(doc=doc1)
        with guard:
            # Симулируем открытие второго чертежа при пакетной печати
            guard.register_doc(doc2)

        # Проверяем doc1
        doc1_temp_view.Delete.assert_called_once()
        doc1_user_view.Delete.assert_not_called()

        # Проверяем doc2
        doc2_temp_view.Delete.assert_called_once()
        doc2_user_view.Delete.assert_not_called()

    def test_views_collection_fallback_indexing(self):
        """
        Если коллекция Views не поддерживает прямое преобразование list(views)
        (например, COM Dispatch коллекция без __iter__), используется перебор по Count и Item(idx).
        """
        view_temp = MagicMock(Name="_SHT_PLOT_VIEW_SPECIAL")
        view_user = MagicMock(Name="MyFavoriteView")

        non_iterable_views = MockNonIterableViews([view_temp, view_user])
        doc = create_mock_doc()
        doc.Views = non_iterable_views

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            pass

        view_temp.Delete.assert_called_once()
        view_user.Delete.assert_not_called()

    def test_view_delete_exception_handled_gracefully(self):
        """
        Если при удалении одного из видов возникает ошибка (например, вид заблокирован),
        очистка остальных видов продолжается без падения программы.
        """
        view_locked = MagicMock(Name="_SHT_PLOT_VIEW_LOCKED")
        view_locked.Delete.side_effect = RuntimeError("Вид заблокирован")

        view_normal = MagicMock(Name="_SHT_PLOT_VIEW_OK")

        doc = create_mock_doc(views=[view_locked, view_normal])

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            pass

        # Несмотря на ошибку в первом виде, второй вид должен быть успешно удален
        view_locked.Delete.assert_called_once()
        view_normal.Delete.assert_called_once()

    def test_doc_views_empty_or_none(self):
        """Если у документа Views равен None или пустой, очистка завершается без ошибок."""
        doc = create_mock_doc()
        doc.Views = None

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            pass

        self.assertFalse(guard._is_active)


# ============================================================================
# 3. Тесты восстановления активного листа и активного документа
# ============================================================================

class TestAutoCADStateGuardLayoutAndDocRestoration(unittest.TestCase):
    """
    Тестирование возврата исходного листа (ActiveLayout), исходного документа и снятия подсветки.
    """

    def test_active_layout_restored_to_model(self):
        """
        Если исходный активный лист был 'Model', а внутри контекста переключились на 'Layout1',
        при выходе ActiveLayout возвращается на 'Model'.
        """
        doc = create_mock_doc(initial_layout="Model")
        model_layout = doc.ActiveLayout

        paper_layout = MagicMock()
        paper_layout.Name = "Layout1"

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            # Симулируем переключение листа на вкладку Layout1
            doc.ActiveLayout = paper_layout

        # На выходе должно быть вызвано восстановление через Layouts.Item('Model')
        doc.Layouts.Item.assert_called_with("Model")

    def test_active_layout_restoration_fallback_to_modelspace(self):
        """
        Если вызов Layouts.Item('Model') завершается ошибкой,
        используется резервный вариант doc.ModelSpace.Layout.
        """
        doc = create_mock_doc(initial_layout="Model")
        doc.Layouts.Item.side_effect = RuntimeError("Item не найден")

        paper_layout = MagicMock()
        paper_layout.Name = "Layout1"

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            doc.ActiveLayout = paper_layout

        # Проверяем, что сработал fallback и ActiveLayout равен ModelSpace.Layout
        self.assertEqual(doc.ActiveLayout, doc.ModelSpace.Layout)

    def test_active_layout_restored_to_paper_layout(self):
        """
        Если исходный лист был листом оформления (например, 'Лист 1'),
        а внутри контекста переключились на 'Model', при выходе возвращается 'Лист 1'.
        """
        doc = create_mock_doc(initial_layout="Лист 1")
        initial_layout_obj = doc.ActiveLayout

        model_layout = MagicMock()
        model_layout.Name = "Model"

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            doc.ActiveLayout = model_layout

        doc.Layouts.Item.assert_called_with("Лист 1")

    def test_active_layout_not_modified_if_unchanged(self):
        """Если активный лист внутри контекста не изменялся, присвоение ActiveLayout не вызывается."""
        doc = create_mock_doc(initial_layout="Model")

        guard = AutoCADStateGuard(doc=doc)
        with guard:
            # Лист не трогали
            pass

        doc.Layouts.Item.assert_not_called()

    def test_activate_document_called_on_exit(self):
        """При выходе вызывается connector.activate_document(initial_active_doc)."""
        doc = create_mock_doc(name="active.dwg")
        connector = create_mock_connector(doc=doc)

        guard = AutoCADStateGuard(connector=connector, doc=doc)
        with guard:
            pass

        connector.activate_document.assert_called_once_with(doc)

    def test_activate_document_fallback_to_app_active_document(self):
        """
        Если у коннектора нет метода activate_document,
        устанавливается connector.app.ActiveDocument = initial_active_doc.
        """
        doc = create_mock_doc(name="active.dwg")
        connector = MagicMock(spec=["app", "clear_highlight"])
        connector.app = MagicMock()

        guard = AutoCADStateGuard(connector=connector, doc=doc)
        with guard:
            pass

        self.assertEqual(connector.app.ActiveDocument, doc)

    def test_clear_highlight_called_on_exit(self):
        """При выходе вызывается connector.clear_highlight() для снятия визуальной подсветки."""
        doc = create_mock_doc()
        connector = create_mock_connector(doc=doc)

        guard = AutoCADStateGuard(connector=connector, doc=doc)
        with guard:
            pass

        connector.clear_highlight.assert_called_once()

    def test_clear_highlight_exception_handled_safely(self):
        """Ошибка при снятии подсветки не должна приводить к сбою restore()."""
        doc = create_mock_doc()
        connector = create_mock_connector(doc=doc)
        connector.clear_highlight.side_effect = RuntimeError("Ошибка COM при clear_highlight")

        guard = AutoCADStateGuard(connector=connector, doc=doc)
        with guard:
            pass

        # Выход прошел без исключения
        self.assertFalse(guard._is_active)


# ============================================================================
# 4. Тесты устойчивости к сбоям, None и мертвым COM-объектам (Robustness)
# ============================================================================

class TestAutoCADStateGuardRobustness(unittest.TestCase):
    """
    Тестирование работы AutoCADStateGuard при отсутствующих параметрах,
    сбоях COM-объектов и неожиданных исключениях.
    """

    def test_none_connector_and_none_doc(self):
        """Guard безопасно инициализируется и отрабатывает, когда connector=None и doc=None."""
        guard = AutoCADStateGuard(connector=None, doc=None, target_bg_plot=0)

        # Вход и выход должны пройти без единого исключения
        with guard:
            self.assertIsNone(guard.initial_active_doc)
            self.assertEqual(len(guard.saved_vars), 0)

        self.assertFalse(guard._is_active)

    def test_dead_doc_on_enter(self):
        """Если переданный doc мертв (обращение к .Name вызывает ошибку), вход проходит безопасно."""
        dead_doc = DeadComObject()
        guard = AutoCADStateGuard(connector=None, doc=dead_doc, target_bg_plot=0)

        with guard:
            self.assertIsNone(guard.initial_active_doc)

        self.assertFalse(guard._is_active)

    def test_doc_disconnects_during_operation(self):
        """
        Если документ был доступен на старте, но закрыт пользователем во время работы,
        restore() безопасно пропускает обращение к закрытому объекту.
        """
        disconnecting_doc = DisconnectingDoc()
        guard = AutoCADStateGuard(connector=None, doc=disconnecting_doc, target_bg_plot=0)

        with guard:
            self.assertEqual(disconnecting_doc.GetVariable("BACKGROUNDPLOT"), 0)
            # Симулируем закрытие документа пользователем во время печати
            disconnecting_doc.disconnect()

        # При выходе не должно быть падения из-за RPC server unavailable
        self.assertFalse(guard._is_active)

    def test_register_doc_ignores_none_and_dead_docs(self):
        """Метод register_doc корректно игнорирует None и мертвые документы."""
        guard = AutoCADStateGuard(connector=None, doc=None)

        guard.register_doc(None)
        guard.register_doc(DeadComObject())

        self.assertEqual(len(guard.touched_docs), 0)

    def test_register_doc_prevents_duplicate_registration(self):
        """Повторная регистрация одного и того же чертежа не создает дубликатов в touched_docs."""
        doc1 = create_mock_doc(name="doc1.dwg", full_path="C:/drawings/doc1.dwg")
        doc1_alias = create_mock_doc(name="doc1.dwg", full_path="c:/DRAWINGS/DOC1.DWG")

        guard = AutoCADStateGuard(doc=doc1)
        guard.__enter__()

        # Регистрируем повторно сам объект и алиас с тем же путем
        guard.register_doc(doc1)
        guard.register_doc(doc1_alias)

        self.assertEqual(len(guard.touched_docs), 1)
        guard.__exit__(None, None, None)

    def test_get_sysvar_and_set_sysvar_without_doc(self):
        """get_sysvar возвращает None, а set_sysvar возвращает False, если нет доступного чертежа."""
        guard = AutoCADStateGuard(connector=None, doc=None)

        val = guard.get_sysvar("FILEDIA")
        self.assertIsNone(val)

        success = guard.set_sysvar("FILEDIA", 1)
        self.assertFalse(success)

        # Передача value=None также возвращает False
        self.assertFalse(guard.set_sysvar("FILEDIA", None))

    def test_restore_never_crashes_on_total_com_failure(self):
        """
        Даже если при восстановлении параметров, видов, листа и чертежа
        каждый вызов бросает исключение, restore() не выбрасывает ошибку наружу.
        """
        doc = create_mock_doc()
        doc.SetVariable.side_effect = RuntimeError("SetVariable COM error")
        doc.Layouts.Item.side_effect = RuntimeError("Layouts COM error")
        doc.Views = [MagicMock(Name="_SHT_PLOT_VIEW_ERR", Delete=MagicMock(side_effect=RuntimeError("Delete error")))]

        connector = MagicMock()
        connector.activate_document.side_effect = RuntimeError("ActivateDoc error")
        connector.clear_highlight.side_effect = RuntimeError("Highlight error")

        guard = AutoCADStateGuard(connector=connector, doc=doc, target_bg_plot=0)
        # restore() не должен выбросить исключение
        guard.__enter__()
        guard.restore()
        guard.__exit__(None, None, None)

    def test_deferred_sysvar_save_on_late_doc_registration(self):
        """
        Если контекст открыт без чертежа (печать из пустой сессии),
        а чертеж открывается и регистрируется позже через register_doc,
        переменные считываются и target_bg_plot применяется с задержкой.
        """
        late_doc = create_mock_doc(name="late.dwg", sysvars={"BACKGROUNDPLOT": 2})

        guard = AutoCADStateGuard(connector=None, doc=None, target_bg_plot=0)
        with guard:
            self.assertEqual(len(guard.saved_vars), 0)
            # Регистрируем чертеж уже внутри активного контекста
            guard.register_doc(late_doc)
            self.assertEqual(guard.saved_vars["BACKGROUNDPLOT"], 2)
            self.assertEqual(late_doc._vars_store["BACKGROUNDPLOT"], 0)

        # При выходе значение восстанавливается
        self.assertEqual(late_doc._vars_store["BACKGROUNDPLOT"], 2)


if __name__ == "__main__":
    unittest.main()
