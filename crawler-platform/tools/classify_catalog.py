"""按审核过的版本清单补用途；默认预览，--apply 才写入独立元数据。"""
import argparse
import hashlib
import json
from pathlib import Path
from runtime.catalog import Catalog, classification


def migrate(root, mapping, apply=False):
    catalog = Catalog(root)
    documents = json.loads(Path(mapping).read_text(encoding='utf-8'))
    active = {item['id'] for item in catalog.list()}
    planned = []
    for item in documents:
        document = catalog.get(item['id'])
        metadata = classification(item)
        planned.append(dict(id=item['id'], name=document['name'], active=item['id'] in active, **metadata))
    snapshot = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for pattern in ('*.json', '.heads/*.json') for path in Path(root).glob(pattern)}
    if apply:
        for item in planned:
            catalog.classify(item['id'], item['purpose'], item['task_name'])
        after = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for pattern in ('*.json', '.heads/*.json') for path in Path(root).glob(pattern)}
        if snapshot != after:
            raise RuntimeError('模板或活动指针发生变化，请立即核对')
    return {'applied': apply, 'versions_and_heads_unchanged': True, 'classified': planned}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', default='/var/lib/crawler-dev/catalog')
    parser.add_argument('--mapping', default='deploy/catalog-classifications.json')
    parser.add_argument('--apply', action='store_true')
    options = parser.parse_args()
    print(json.dumps(migrate(Path(options.catalog), options.mapping, options.apply), ensure_ascii=False))
