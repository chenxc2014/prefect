"""只在真实运行完成、认证下载成功且逐字段对账通过后生成验收材料。"""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from runtime.artifacts import read_rows,validate_file
private=root/'.local/sites/qjdyf-maxun'
state=json.loads((private/'run-status.json').read_text(encoding='utf-8'))
ui=json.loads((private/'ui-acceptance.json').read_text(encoding='utf-8'))
assert state['state']=='COMPLETED' and ui['passed'] and ui['run_id']==state['id']
file=private/'商品流向_20261112_Maxun.xlsx';digest=hashlib.sha256(file.read_bytes()).hexdigest()
assert digest==state['artifacts'][0]['sha256']
actual=read_rows(file);baseline=read_rows(root/'.local/sites/qjdyf/商品流向_20261112_人工取证.xlsx')
canonical=lambda rows:sorted(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':')) for row in rows)
assert len(actual)==3 and Counter(canonical(actual))==Counter(canonical(baseline))
checks=validate_file(file,{'min_rows':1,'required_columns':['时间','商品编码','数量'],'date_columns':['时间'],'date_range':['2026-11-12','2026-11-12']})
runs=json.loads((private/'maxun-runs.json').read_text(encoding='utf-8'))
completed=[r for r in runs if r['status']=='success' and 'Action ' not in r.get('log','') and r.get('name','').startswith('平台执行 ·') and (private/(r['runId']+'-'+state['artifacts'][0]['name'])).exists() and hashlib.sha256((private/(r['runId']+'-'+state['artifacts'][0]['name'])).read_bytes()).hexdigest()==digest]
latest=max(completed,key=lambda r:datetime.strptime(r['startedAt'],'%m/%d/%Y, %I:%M:%S %p'))
detail=json.loads((private/('maxun-'+latest['runId']+'.json')).read_text(encoding='utf-8'))
method_file=private/(latest['runId']+'-download-method.json')
method=json.loads(method_file.read_text(encoding='utf-8')) if method_file.exists() else None
published=json.loads((private/'published.json').read_text())
document=json.loads((root/'deploy/sites/qjdyf-maxun/template.json').read_text(encoding='utf-8'))
report={'date':'2026-11-18','passed':True,'website':'https://wx.qjdyf.cn/supplier-front-2.0/#/login','module':'商品对接 → 商品流向','query_date':['2026-11-12','2026-11-12'],'engine':'maxun','node':'linux-169','source_robot_id':'66af1f99-bd71-4c86-b190-8d96a7b6176d','published_robot_id':document['task']['robot_id'],'template_id':published['id'],'prefect_run_id':state['id'],'maxun_run_id':latest['runId'],'ui':ui,'artifact':{'name':state['artifacts'][0]['name'],'size':file.stat().st_size,'sha256':digest,'validation':checks,'columns':list(actual[0])},'comparison':{'baseline':'此前人工取证文件','row_count':3,'all_fields_equal_ignoring_order':True,'ordered_equal':actual==baseline,'canonical_rows_sha256':hashlib.sha256('\n'.join(canonical(actual)).encode()).hexdigest()},'download_capture':method,'earlier_completed_prefect_run':'e06fcc34-90fc-4b6b-9531-e0f403e776c6','failed_attempts':[{'prefect_run_id':'e97a207b-acc2-4ea4-8aa4-369fe0d4eb68','reason':'未捕获下载，产物校验拒绝通过'},{'prefect_run_id':'c312f8df-1409-4838-8bde-6c2e85d16eaa','reason':'已导出文件，但中文对象键内部读取返回404'},{'prefect_run_id':'99fe495d-5468-46e9-b46d-40c1149f8179','reason':'原生下载事件间歇缺失，新增Blob原始字节捕获'}],'schedules_enabled':False,'windows_167_accessed':False,'limitations':['仅对2026-11-12单日完成业务对账，其他日期需复核','图片验证码采用识别和有限重试，不保证所有验证码都能成功','当前为单开发管理员环境，未完成生产级多用户权限和高可用验收']}
report['failed_attempts'].append({'prefect_run_id':'a72b3641-64f7-4ef9-9f07-b913cf15190d','reason':'重复导出未取得文件，运行按失败保留；根因尚未完全确认'})
report['limitations'].append('重复导出曾出现未返回文件；本次单日通过不代表短时重复导出或长期无人值守稳定性已经验收')
report['download_validation']={'actual_final_method':method,'blob_fallback':'受控浏览器测试通过，覆盖链接点击和分离节点事件','network_response_fallback':'受控浏览器测试通过，保留响应原始字节','site_native_response_type':'application/binary;charset=UTF-8','repeated_export_failures_fully_resolved':False}
report['limitations'].append('Maxun 原生结果页的中文对象链接仍有编码兼容问题；当前使用已验证的采集管理平台归档下载')
report['recording_log_hardening']={'keystroke_values_removed':True,'compiled_overlay_syntax_checked':True,'business_actions_changed':False}
(root/'doc/千金商品流向Maxun验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':True,'prefect_run_id':state['id'],'rows':len(actual),'same_fields':True,'download_capture':method},ensure_ascii=False))
