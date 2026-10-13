import zlib
import glob
import re

for p in glob.glob(r'C:\Users\Admin\AppData\Roaming\Autodesk\AutoCAD 2021\R24.0\rus\Plotters\*.pc3'):
    try:
        data = open(p, 'rb').read()
        if data.startswith(b"PIAFILEVERSION_2.0,PC3VER1,compress\r\npmzlibcodec") and len(data) > 60:
            txt = zlib.decompress(data[60:]).decode('latin1', errors='replace')
            m = re.search(r'name="View_New_File\s*\r?\n\s*value=(\w+)', txt)
            if m:
                print(f"{p.split('\\')[-1]}: View_New_File = {m.group(1)}")
            else:
                if 'View_New_File' in txt:
                    print(f"{p.split('\\')[-1]}: View_New_File present but regex not matched")
    except Exception as e:
        print(f"Error {p}: {e}")
