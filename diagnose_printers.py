from core.autocad_connector import AutoCADConnector

connector = AutoCADConnector()
connector.connect()

layout = connector.doc.ModelSpace.Layout
layout.ConfigName = "DWG To PDF.pc3"
layout.RefreshPlotDeviceInfo()

names = layout.GetCanonicalMediaNames()
print("Доступные форматы в DWG To PDF.pc3:")
for sys_name in names:
    local_name = layout.GetLocaleMediaName(sys_name)
    if "full bleed" in local_name.lower():
        print(f"{sys_name} -> {local_name}")
        
connector.disconnect()
