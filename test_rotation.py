from core.autocad_connector import AutoCADConnector

def test_rotation():
    connector = AutoCADConnector()
    connector.connect()
    layout = connector.doc.ModelSpace.Layout
    
    # Пытаемся получить размеры
    w, h = layout.GetPaperSize()
    print(f"Текущий размер бумаги: {w} x {h}")
    print(f"Текущий поворот (PlotRotation): {layout.PlotRotation}")

if __name__ == "__main__":
    test_rotation()
