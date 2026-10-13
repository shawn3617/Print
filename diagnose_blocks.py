from core.autocad_connector import AutoCADConnector

def inspect_blocks():
    connector = AutoCADConnector()
    connector.connect()
    
    print("Ищем блоки...")
    for i in range(connector.doc.ModelSpace.Count):
        obj = connector.doc.ModelSpace.Item(i)
        if getattr(obj, 'EntityName', '') == 'AcDbBlockReference':
            name = ""
            try:
                name = obj.EffectiveName
            except:
                try: name = obj.Name
                except: pass
                
            if name:
                min_pt, max_pt = obj.GetBoundingBox()
                w = max_pt[0] - min_pt[0]
                h = max_pt[1] - min_pt[1]
                
                print(f"Блок '{name}':")
                print(f"  BoundingBox WxH: {w:.1f} x {h:.1f}")
                print(f"  InsertionPoint: {obj.InsertionPoint}")
                print(f"  XScale: {obj.XScaleFactor}, YScale: {obj.YScaleFactor}")
                
if __name__ == "__main__":
    inspect_blocks()
