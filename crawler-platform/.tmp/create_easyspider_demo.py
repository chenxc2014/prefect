"""根据上游字段结构生成自有模拟页面任务，定位依据见 tools/demo_site.py。"""
from pathlib import Path
import json

common = dict(history=1, tabIndex=0, useLoop=False, xpath='', iframe=False, wait=1, waitType=0, beforeJS='', beforeJSWaitTime=0, afterJS='', afterJSWaitTime=0, waitElement='', waitElementTime=10, waitElementIframeIndex=0, scrollType=0, scrollCount=1, scrollWaitTime=1)
def node(number, option, title, **parameters):
    return dict(index=number, id=number, parentId=0, type=0, option=option, title=title, sequence=[], isInLoop=False, parameters=dict(common, **parameters))

graph = [node(0, 0, '根节点'), node(1, 1, '打开模拟销售页', url='http://127.0.0.1:8766', links='http://127.0.0.1:8766', maxWaitTime=10, cookies=''), node(2, 4, '填写开始日期', xpath='//*[@id="begindate"]', value='{{begindate}}', index=0), node(3, 2, '查询', xpath='//*[@id="search"]', clickWay=0, newTab=0, maxWaitTime=10, alertHandleType=0), node(4, 2, '导出 CSV', xpath='//*[@id="export"]', clickWay=0, newTab=0, maxWaitTime=10, alertHandleType=0)]
graph[0]['sequence'] = [1, 2, 3, 4]
task = dict(name='模拟销售日期查询与导出', version='0.6.3', links='http://127.0.0.1:8766', url=['http://127.0.0.1:8766'], graph=graph, outputParameters=[], containJudge=False, outputFormat='csv', cloudflare=0, environment=0, browser='chrome', saveName='result', quitWaitTime=2, recordLog=True, pauseKey='p', saveThreshold=10, dataWriteMode=1)
directory = Path('deploy/examples')
directory.mkdir(exist_ok=True)
(directory / 'demo-task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
document = dict(engine='easyspider', name=task['name'], node='linux-169', task=task, bindings={'begindate': ['graph.2.parameters.value']}, defaults={'begindate': '2026-11-01'}, checks={'required_files': ['Data/Task_0/result/files/*.csv'], 'min_rows': 6, 'required_columns': ['id','quantity']})
(directory / 'demo-template.json').write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
