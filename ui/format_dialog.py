"""
Диалоговое окно ручного уточнения формата и масштаба листа (ui/format_dialog.py).

Позволяет пользователю:
- Видеть размеры рамки в чертеже, текущий формат, вычисленный масштаб и основание выбора;
- Быстро переключаться между предложенными вариантами при неоднозначности (например, A2 М1:100 vs A4 М1:200);
- Вручную выбрать любой формат по ГОСТ 2.301-68 и задать масштаб;
- Применить выбранный формат к одному или ко всем выделенным листам.
"""

from typing import List, Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QRadioButton, QButtonGroup, QGroupBox,
    QCheckBox, QDialogButtonBox
)
from PySide6.QtCore import Qt

from core.models import Frame, ALL_FORMATS, get_paper_size_mm


class FormatSelectDialog(QDialog):
    def __init__(
        self,
        parent=None,
        frame: Optional[Frame] = None,
        available_plotter_formats: Optional[List[str]] = None,
        selected_count: int = 1
    ):
        super().__init__(parent)
        self.frame = frame
        self.selected_count = selected_count
        self.available_plotter_formats = available_plotter_formats or []

        num_str = getattr(frame, "sheet_number", "") if frame else ""
        self.setWindowTitle(f"Уточнение формата листа {num_str}".strip())
        self.setMinimumWidth(460)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 1. Информационная панель текущего листа
        info_box = QGroupBox("Параметры листа в чертеже")
        info_layout = QVBoxLayout(info_box)
        info_layout.setSpacing(4)

        if self.frame:
            sheet_title = self.frame.sheet_name or "Без наименования"
            num_display = self.frame.sheet_number or "б/н"
            w_draw = abs(self.frame.max_point[0] - self.frame.min_point[0])
            h_draw = abs(self.frame.max_point[1] - self.frame.min_point[1])
            curr_fmt = self.frame.paper_format or "Не определен"
            curr_scale = getattr(self.frame, "scale", 1) or 1
            reason = getattr(self.frame, "format_reason", "") or "Геометрия"

            lbl_sheet = QLabel(f"<b>Лист {num_display}:</b> {sheet_title}")
            lbl_size = QLabel(f"Размеры рамки в чертеже: <b>{w_draw:.0f} × {h_draw:.0f}</b> ед.")
            lbl_curr = QLabel(f"Текущий формат: <b>{curr_fmt}</b> (масштаб 1:<b>{curr_scale}</b>)")
            lbl_reason = QLabel(f"Основание выбора: <i>{reason}</i>")
            lbl_reason.setStyleSheet("color: #666;")

            info_layout.addWidget(lbl_sheet)
            info_layout.addWidget(lbl_size)
            info_layout.addWidget(lbl_curr)
            info_layout.addWidget(lbl_reason)
        else:
            w_draw, h_draw = 59400.0, 42000.0
            info_layout.addWidget(QLabel("Лист не выбран"))

        layout.addWidget(info_box)

        # 2. Блок предложенных вариантов при неоднозначности
        self.btn_group = QButtonGroup(self)
        possible = getattr(self.frame, "possible_formats", []) if self.frame else []

        if possible and len(possible) > 1:
            cand_box = QGroupBox("⚠️ Предложенные варианты при неоднозначности")
            cand_box.setStyleSheet("QGroupBox { font-weight: bold; }")
            cand_layout = QVBoxLayout(cand_box)
            cand_layout.setSpacing(6)

            curr_fmt = self.frame.paper_format if self.frame else ""
            curr_scale = getattr(self.frame, "scale", 1) if self.frame else 1

            for idx, (fmt_name, sc) in enumerate(possible):
                is_selected = (fmt_name == curr_fmt and sc == curr_scale)
                rb = QRadioButton(f"{fmt_name} — масштаб 1:{sc}")
                rb.setChecked(is_selected or idx == 0)
                self.btn_group.addButton(rb, idx)
                cand_layout.addWidget(rb)

                # При клике на радиокнопку синхронизируем выпадающие списки ручного выбора
                rb.toggled.connect(lambda checked, f=fmt_name, s=sc: self._on_candidate_toggled(checked, f, s))

            layout.addWidget(cand_box)

        # 3. Ручной выбор формата и масштаба
        manual_box = QGroupBox("Выбор формата и масштаба вручную")
        manual_layout = QVBoxLayout(manual_box)
        manual_layout.setSpacing(8)

        # Формат бумаги
        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("Формат бумаги:"))
        self.combo_format = QComboBox()
        standard_order = ["A4", "A3", "A2", "A1", "A0"]
        ext_order = sorted([f for f in ALL_FORMATS.keys() if f not in standard_order])
        all_ordered = standard_order + ext_order
        for fmt in all_ordered:
            pw, ph = ALL_FORMATS[fmt]
            self.combo_format.addItem(f"{fmt} ({pw} × {ph} мм)", fmt)

        # Выбираем текущий формат
        curr_fmt = getattr(self.frame, "paper_format", "A2") or "A2"
        idx = self.combo_format.findData(curr_fmt)
        if idx >= 0:
            self.combo_format.setCurrentIndex(idx)
        self.combo_format.currentIndexChanged.connect(self._update_calculated_preview)
        row_fmt.addWidget(self.combo_format)
        manual_layout.addLayout(row_fmt)

        # Масштаб (1 : N)
        row_scale = QHBoxLayout()
        row_scale.addWidget(QLabel("Масштаб (1 : N):"))
        self.combo_scale = QComboBox()
        self.combo_scale.setEditable(True)
        common_scales = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]
        for sc in common_scales:
            self.combo_scale.addItem(str(sc), sc)

        curr_scale = getattr(self.frame, "scale", 100) or 1
        scale_idx = self.combo_scale.findData(curr_scale)
        if scale_idx >= 0:
            self.combo_scale.setCurrentIndex(scale_idx)
        else:
            self.combo_scale.setEditText(str(curr_scale))

        self.combo_scale.currentTextChanged.connect(self._update_calculated_preview)
        row_scale.addWidget(self.combo_scale)
        manual_layout.addLayout(row_scale)

        # Подсказка о физическом размере
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet("color: #0d6efd; font-size: 11px;")
        manual_layout.addWidget(self.lbl_preview)

        layout.addWidget(manual_box)

        # 4. Чекбокс пакетного применения
        self.chk_apply_all = None
        if self.selected_count > 1:
            self.chk_apply_all = QCheckBox(
                f"Применить этот формат ко всем выделенным листам ({self.selected_count} шт.)"
            )
            layout.addWidget(self.chk_apply_all)

        # 5. Кнопки Ok / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Применить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_calculated_preview()

    def _on_candidate_toggled(self, checked: bool, fmt_name: str, scale_val: int):
        if not checked:
            return
        idx = self.combo_format.findData(fmt_name)
        if idx >= 0:
            self.combo_format.setCurrentIndex(idx)
        s_idx = self.combo_scale.findData(scale_val)
        if s_idx >= 0:
            self.combo_scale.setCurrentIndex(s_idx)
        else:
            self.combo_scale.setEditText(str(scale_val))
        self._update_calculated_preview()

    def _update_calculated_preview(self):
        fmt = self.get_selected_format()
        sc = self.get_selected_scale()
        fw, fh = ALL_FORMATS.get(fmt, (594, 420))

        if self.frame:
            w_draw = max(abs(self.frame.max_point[0] - self.frame.min_point[0]), abs(self.frame.max_point[1] - self.frame.min_point[1]))
            h_draw = min(abs(self.frame.max_point[0] - self.frame.min_point[0]), abs(self.frame.max_point[1] - self.frame.min_point[1]))
            w_mm = w_draw / sc if sc > 0 else 0
            h_mm = h_draw / sc if sc > 0 else 0
            err = abs(w_mm - fw) + abs(h_mm - fh)
            self.lbl_preview.setText(
                f"Размер в масштабе 1:{sc}: <b>{w_mm:.1f} × {h_mm:.1f} мм</b> "
                f"(ГОСТ {fmt}: {fw} × {fh} мм, погрешность: {err:.1f} мм)"
            )
        else:
            self.lbl_preview.setText(f"Формат ГОСТ {fmt}: <b>{fw} × {fh} мм</b>")

    def get_selected_format(self) -> str:
        data = self.combo_format.currentData()
        return str(data) if data else self.combo_format.currentText().split()[0]

    def get_selected_scale(self) -> int:
        txt = self.combo_scale.currentText().strip()
        try:
            val = int(txt)
            return max(1, val)
        except ValueError:
            return 1

    def apply_to_selected_rows(self) -> bool:
        return self.chk_apply_all.isChecked() if self.chk_apply_all else False
