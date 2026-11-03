"""
_retry_busy повторяет только «AutoCAD занят» (AttributeError в exe и COM-ошибки занятости),
а настоящие COM-ошибки («Неверный ввод» и т.п.) пробрасывает сразу.
"""
import unittest
from unittest.mock import patch, MagicMock

import pythoncom

from core.autocad_connector import (
    _retry_busy, _is_busy_com_error,
    RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER, DISP_E_EXCEPTION,
)

E_INVALIDARG = -2147024809  # 0x80070057
ACAD_BAD_INPUT = -2145386493  # пример настоящей ошибки AutoCAD внутри DISP_E_EXCEPTION


def com_err(hresult, text="", excepinfo=None):
    return pythoncom.com_error(hresult, text, excepinfo, None)


@patch("time.sleep", return_value=None)
class TestRetryBusy(unittest.TestCase):

    def test_busy_hresult_is_retried(self, _sleep):
        func = MagicMock(side_effect=[com_err(RPC_E_CALL_REJECTED, "Вызов был отклонен."),
                                      com_err(RPC_E_SERVERCALL_RETRYLATER), "ok"])
        self.assertEqual(_retry_busy(func), "ok")
        self.assertEqual(func.call_count, 3)

    def test_attribute_error_is_retried(self, _sleep):
        func = MagicMock(side_effect=[AttributeError("Open.ModelSpace"), "ok"])
        self.assertEqual(_retry_busy(func), "ok")
        self.assertEqual(func.call_count, 2)

    def test_busy_inside_disp_exception_is_retried(self, _sleep):
        excepinfo = (0, "AutoCAD", "Вызов был отклонен", None, 0, RPC_E_CALL_REJECTED)
        func = MagicMock(side_effect=[com_err(DISP_E_EXCEPTION, "Ошибка.", excepinfo), "ok"])
        self.assertEqual(_retry_busy(func), "ok")
        self.assertEqual(func.call_count, 2)

    def test_real_com_error_raised_immediately(self, _sleep):
        func = MagicMock(side_effect=com_err(E_INVALIDARG, "Параметр задан неверно."))
        with self.assertRaises(pythoncom.com_error):
            _retry_busy(func, max_attempts=20)
        self.assertEqual(func.call_count, 1)

    def test_real_autocad_error_raised_immediately(self, _sleep):
        excepinfo = (0, "AutoCAD.Application", "Неверный ввод", None, 0, ACAD_BAD_INPUT)
        func = MagicMock(side_effect=com_err(DISP_E_EXCEPTION, "Ошибка.", excepinfo))
        with self.assertRaises(pythoncom.com_error):
            _retry_busy(func, max_attempts=20)
        self.assertEqual(func.call_count, 1)

    def test_gives_up_after_max_attempts(self, _sleep):
        func = MagicMock(side_effect=com_err(RPC_E_CALL_REJECTED))
        with self.assertRaises(pythoncom.com_error):
            _retry_busy(func, max_attempts=5)
        self.assertEqual(func.call_count, 5)

    def test_other_exceptions_not_retried(self, _sleep):
        func = MagicMock(side_effect=RuntimeError("плоттер не поддерживает формат"))
        with self.assertRaises(RuntimeError):
            _retry_busy(func)
        self.assertEqual(func.call_count, 1)

    def test_is_busy_by_text(self, _sleep):
        self.assertTrue(_is_busy_com_error(com_err(-1, "Call was rejected by callee.")))
        self.assertFalse(_is_busy_com_error(com_err(E_INVALIDARG, "Параметр задан неверно.")))


if __name__ == "__main__":
    unittest.main()
