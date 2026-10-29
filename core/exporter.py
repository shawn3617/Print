import csv
from typing import List
from core.models import Frame


class SheetExporter:
    HEADERS = [
        "№ п/п",
        "Лист",
        "Обозначение документа",
        "Наименование листа",
        "Объект строительства",
        "Здание / сооружение",
        "Формат",
        "Чертеж",
        "Источник"
    ]

    @classmethod
    def export(cls, frames: List[Frame], filepath: str):
        """Экспортирует список листов в файл (.xlsx или .csv) в зависимости от расширения."""
        if filepath.lower().endswith(".xlsx"):
            cls.export_to_xlsx(frames, filepath)
        else:
            cls.export_to_csv(frames, filepath)

    @classmethod
    def export_to_csv(cls, frames: List[Frame], filepath: str):
        """Экспорт в CSV с разделителем ';' и кодировкой utf-8-sig для корректного открытия в Excel."""
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(cls.HEADERS)
            for i, f_obj in enumerate(frames, 1):
                writer.writerow([
                    i,
                    f_obj.sheet_number,
                    f_obj.doc_code or "",
                    f_obj.sheet_name,
                    f_obj.object_name or "",
                    f_obj.building_name or "",
                    f_obj.paper_format,
                    f_obj.dwg_name or "",
                    f_obj.source_type or ""
                ])

    @classmethod
    def export_to_xlsx(cls, frames: List[Frame], filepath: str):
        """Экспорт в нативный Excel (.xlsx) со стилями заголовков и автоподбором ширины колонок."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ведомость листов"

        # Заголовки
        ws.append(cls.HEADERS)

        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="313244", end_color="313244", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin', color='D0D0D0'),
            right=Side(style='thin', color='D0D0D0'),
            top=Side(style='thin', color='D0D0D0'),
            bottom=Side(style='thin', color='D0D0D0')
        )

        for col_idx in range(1, len(cls.HEADERS) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        data_font = Font(name="Segoe UI", size=10)
        # Данные
        for i, f_obj in enumerate(frames, 1):
            row_num = i + 1
            ws.append([
                i,
                f_obj.sheet_number,
                f_obj.doc_code or "",
                f_obj.sheet_name,
                f_obj.object_name or "",
                f_obj.building_name or "",
                f_obj.paper_format,
                f_obj.dwg_name or "",
                f_obj.source_type or ""
            ])
            for col_idx in range(1, len(cls.HEADERS) + 1):
                cell = ws.cell(row=row_num, column=col_idx)
                cell.font = data_font
                cell.border = thin_border
                if col_idx in (1, 2, 7, 9):
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

        # Автоширина колонок
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                val = str(cell.value or "")
                max_len = max(max_len, len(val))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 10)

        wb.save(filepath)
