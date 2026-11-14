"""核对自动归档文件与人工浏览器取证的业务数据等价性。"""
import hashlib
import json
from pathlib import Path
from urllib.request import Request,urlopen
from tools.dev_api import DevApi
from runtime.artifacts import read_rows,validate_file


def verify():
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'doc/千金商品流向自动采集.json').read_text(encoding='utf-8'))
    api=DevApi()
    artifact=report['status']['artifacts'][0]
    req=Request(api.base.removesuffix('/api')+artifact['url'],headers={'Authorization':api.auth})
    with urlopen(req,context=api.context,timeout=30) as response:
        content=response.read()
    assert hashlib.sha256(content).hexdigest()==artifact['sha256']
    file=root/'.local/sites/qjdyf/商品流向_20261112_自动采集.xlsx'
    file.write_bytes(content)
    checks={'min_rows':1,'required_columns':['时间','商品编码','数量'],'date_columns':['时间'],'date_range':['2026-11-12','2026-11-12']}
    report['file_validation']=validate_file(file,checks)
    manual=file.with_name('商品流向_20261112_人工取证.xlsx')
    normalize=lambda rows:sorted(json.dumps(row,ensure_ascii=False,sort_keys=True) for row in rows)
    report['equivalent_to_manual']=normalize(read_rows(file))==normalize(read_rows(manual))
    assert report['equivalent_to_manual'],'自动与人工取证业务数据不一致'
    report['local_file']=str(file.relative_to(root))
    (root/'doc/千金商品流向自动采集.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'file_validation':report['file_validation'],'equivalent_to_manual':True},ensure_ascii=False))
