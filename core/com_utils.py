import time

def com_retry(func, max_attempts: int = 20, delay: float = 0.3):
    """
    Выполняет COM-вызов с автоматическими повторными попытками при ошибках занятости AutoCAD:
    - RPC_E_CALL_REJECTED (0x80010001 / -2147418111)
    - RPC_E_SERVERCALL_RETRYLATER (0x8001010A / -2147417846)
    """
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            err_str = str(e).lower()
            hresult = getattr(e, "hresult", None)
            if not hresult and hasattr(e, "args") and e.args and isinstance(e.args[0], int):
                hresult = e.args[0]
            if hresult in (-2147418111, -2147417846) or "отклонен" in err_str or "rejected" in err_str:
                time.sleep(delay)
                continue
            raise
    return func()
