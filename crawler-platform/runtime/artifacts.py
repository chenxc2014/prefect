"""只读核验采集表格的表头、数据量及业务日期，不修改原文件。"""
import csv
from datetime import datetime,timedelta
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


def read_rows(file):
    file=Path(file)
    if file.suffix.lower()=='.csv':
        with file.open(encoding='utf-8-sig',newline='') as handle:
            return list(csv.DictReader(handle))
    if file.suffix.lower()=='.xlsx':
        ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(file) as archive:
            shared=[]
            if 'xl/sharedStrings.xml' in archive.namelist():
                shared=[''.join(x.itertext()) for x in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',ns)]
            name=next(n for n in archive.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n))
            result=[]
            for row in ET.fromstring(archive.read(name)).findall('m:sheetData/m:row',ns):
                values={}
                for cell in row.findall('m:c',ns):
                    column=re.match('[A-Z]+',cell.attrib['r']).group()
                    value=cell.find('m:v',ns)
                    if value is not None:
                        value=value.text or ''
                        if cell.get('t')=='s':value=shared[int(value)]
                    else:
                        inline=cell.find('m:is',ns)
                        value=''.join(inline.itertext()) if inline is not None else ''
                    values[column]=value
                result.append(values)
            if not result:return []
            header=result[0]
            return [{title:row.get(column,'') for column,title in header.items()} for row in result[1:] if any(row.values())]
    return None


def validate_file(file,checks):
    rows=read_rows(file)
    if rows is None:
        return {'row_count':None}
    if len(rows)<checks.get('min_rows',1):
        raise RuntimeError('采集行数未达到成功条件')
    for field in checks.get('required_columns',[]):
        if not rows or any(not row.get(field) for row in rows):
            raise RuntimeError('关键字段缺失：'+field)
    for field,expected in checks.get('expected_values',{}).items():
        if not rows or any(row.get(field)!=str(expected) for row in rows):
            raise RuntimeError('字段值不符合运行参数：'+field)
    dates=[]
    for field in checks.get('date_columns',[]):
        for row in rows:
            value=str(row.get(field,''))
            if re.fullmatch(r'\d{8}',value):
                date=datetime.strptime(value,'%Y%m%d').date().isoformat()
            elif re.fullmatch(r'\d+(\.\d+)?',value):
                date=(datetime(1899,12,30)+timedelta(days=float(value))).date().isoformat()
            else:
                date=value.replace('/','-')[:10]
                datetime.strptime(date,'%Y-%m-%d')
            if checks.get('date_range') and not checks['date_range'][0]<=date<=checks['date_range'][1]:
                raise RuntimeError('导出数据日期超出本次查询范围')
            dates.append(date)
    return {'row_count':len(rows),'dates':sorted(set(dates))}
