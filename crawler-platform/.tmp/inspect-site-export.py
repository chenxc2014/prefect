"""保存本次浏览器已下载文件，只读核对工作簿结构与日期列。"""
from pathlib import Path
import hashlib
import json
from datetime import datetime,timedelta
import xml.etree.ElementTree as ET
import zipfile
import sys
sys.stdout.reconfigure(encoding='utf-8')
source=Path(r'C:\Users\chenx\AppData\Local\Temp\playwright-artifacts-OWJ8gj')
files=[p for p in source.iterdir() if p.is_file()]
if not files:
    raise RuntimeError('导出尚未完成')
file=max(files,key=lambda p:p.stat().st_mtime)
body=file.read_bytes()
if not zipfile.is_zipfile(file):
    raise RuntimeError('下载文件不是有效XLSX工作簿，需核查网站导出返回')
target=Path('.local/sites/qjdyf/商品流向_20261112_人工取证.xlsx')
target.write_bytes(body)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime.artifacts import validate_file
summary=validate_file(target,{'min_rows':1,'required_columns':['时间','商品编码','数量'],'date_columns':['时间'],'date_range':['2026-11-12','2026-11-12']})
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
report={'file':str(target),'size':len(body),'sha256':hashlib.sha256(body).hexdigest(),'sheets':[]}
report['validation']=summary
with zipfile.ZipFile(file) as archive:
    shared=[]
    if 'xl/sharedStrings.xml' in archive.namelist():
        shared=[''.join(x.itertext()) for x in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',ns)]
    for name in archive.namelist():
        if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
            rows=[]
            for row in ET.fromstring(archive.read(name)).findall('m:sheetData/m:row',ns):
                values=[]
                for cell in row.findall('m:c',ns):
                    value=cell.find('m:v',ns)
                    value=value.text if value is not None else ''.join(cell.find('m:is',ns).itertext()) if cell.find('m:is',ns) is not None else ''
                    if cell.get('t')=='s':value=shared[int(value)]
                    values.append(value)
                rows.append(values)
            report['sheets'].append({'path':name,'row_count':len(rows),'header':rows[0] if rows else [],'data_rows':max(0,len(rows)-1)})
Path('doc/千金商品流向取证.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
