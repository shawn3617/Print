# Точка входа для сборки exe.
# Делает то же самое, что команда:  python -m ui.main_window
import runpy

runpy.run_module("ui.main_window", run_name="__main__", alter_sys=True)
