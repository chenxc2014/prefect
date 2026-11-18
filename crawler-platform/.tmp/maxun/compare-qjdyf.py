from collections import Counter
import json
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from runtime.artifacts import read_rows,validate_file
root=Path('.local/sites/qjdyf-maxun')
file=next(root.glob('*配送信息.xlsx'))
actual=read_rows(file);baseline=read_rows(Path('.local/sites/qjdyf/商品流向_20261112_人工取证.xlsx'))
as_counter=lambda rows:Counter(json.dumps(row,sort_keys=True,ensure_ascii=False) for row in rows)
report={'actual_rows':len(actual),'baseline_rows':len(baseline),'same_columns':list(actual[0])==list(baseline[0]),'ordered_equal':actual==baseline,'content_equal_ignoring_order':as_counter(actual)==as_counter(baseline),'differing_columns':sorted(set(key for key in actual[0] if Counter(row.get(key) for row in actual)!=Counter(row.get(key) for row in baseline))),'validation':validate_file(file,{'min_rows':1,'required_columns':['时间','商品编码','数量'],'date_columns':['时间'],'date_range':['2026-11-12','2026-11-12']})}
print(json.dumps(report,ensure_ascii=False))
