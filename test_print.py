import os
from core.autocad_connector import AutoCADConnector
from core.scanner import DocumentScanner
import win32com.client
import pythoncom

def test_plot():
    connector = AutoCADConnector()
    connector.connect()
    
    # 1. Сканируем, чтобы получить хотя бы 1 рамку
    scanner = DocumentScanner()
    frames = scanner.scan_document(connector.doc)
    
    if not frames:
        print("Рамки не найдены!")
        return
        
    frame = frames[0]
    print(f"Тестируем печать рамки {frame.sheet_number} ({frame.min_point} - {frame.max_point})")
    
    layout = connector.doc.ModelSpace.Layout
    
    print("Устанавливаем принтер DWG To PDF.pc3...")
    try:
        layout.ConfigName = "DWG To PDF.pc3"
    except Exception as e:
        print(f"Ошибка при установке принтера: {e}")
        
    print("Устанавливаем формат ISO full bleed A2...")
    try:
        layout.CanonicalMediaName = "ISO_full_bleed_A2_(594.00_x_420.00_MM)"
    except Exception as e:
        print(f"Ошибка при установке формата: {e}")
        
    print("Вычисляем окно...")
    try:
        p1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (frame.min_point[0], frame.min_point[1]))
        p2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (frame.max_point[0], frame.max_point[1]))
        layout.SetWindowToPlot(p1, p2)
    except Exception as e:
        print(f"Ошибка SetWindowToPlot: {e}")
        
    print("Устанавливаем PlotType...")
    try:
        layout.PlotType = 4 # acWindow
    except Exception as e:
        print(f"Ошибка PlotType: {e}")
        
    layout.StandardScale = 0
    layout.CenterPlot = True
    
    print("Запускаем PlotToFile...")
    try:
        filepath = os.path.abspath("test_print.pdf")
        connector.doc.Plot.PlotToFile(filepath, "DWG To PDF.pc3")
        print("Печать успешна!")
    except Exception as e:
        print(f"Ошибка PlotToFile: {e}")

if __name__ == "__main__":
    test_plot()
