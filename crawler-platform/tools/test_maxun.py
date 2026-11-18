"""校验流程版本、加密参数与产物成功条件，避免把进程结束误判为采集成功。"""
import copy
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from runtime.maxun import MaxunClient,bind_inputs,execute,fingerprint,storage_url
from runtime.catalog import materialize,validate,bind_account


def robot():
    return {'recording_meta':{'id':str(uuid4()),'name':'测试录制','type':'extract','url':'https://example.com'},
            'recording':{'workflow':[{'where':{'url':'https://example.com'},'what':[{'action':'type','args':['#date','录制密文']}]}]}}


class FakeClient:
    def __init__(self,source,status='success',output=None,log=''):
        self.source=source;self.status=status;self.output=output or {};self.started=False
        self.config={'base_url':'http://127.0.0.1:18080'}
        self.log=log
    def robot(self,identifier):return copy.deepcopy(self.source)
    def duplicate(self,source,name):return copy.deepcopy(source)
    def request(self,path,data=None,method=None):
        if path.endswith('/execute'):
            self.started=True;return {'data':{'runId':str(uuid4())}}
        return {'data':{'status':self.status,'serializableOutput':self.output,'log':self.log}}


class MaxunTest(unittest.TestCase):
    def test_upstream_success_with_action_error_is_still_failure(self):
        source=robot();task={'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)}
        client=FakeClient(source,log='Action platformDownload failed: timeout')
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(RuntimeError,'动作失败'):
            execute(task,{'required_files':['Data/result.csv']},Path(directory)/'run',client=client)
    def test_chinese_object_key_keeps_encoded_percent_in_minio(self):
        config={'storage_public_url':'https://designer.test/objects','storage_internal_url':'http://minio.test:19000'}
        self.assertEqual(storage_url('https://designer.test/objects/bucket/run/%E9%85%8D.xlsx',config),'http://minio.test:19000/bucket/run/%25E9%2585%258D.xlsx')
        self.assertEqual(storage_url('https://designer.test/objects/bucket/run/Screenshot_1',config),'http://minio.test:19000/bucket/run/Screenshot_1')
        for value in ('https://evil.test/objects/file','https://designer.test/objects-other/file','https://designer.test/objects/file?token=value'):
            with self.assertRaises(RuntimeError):storage_url(value,config)
    def test_maxun_secret_binding_does_not_publish_credentials(self):
        source=robot();document={'engine':'maxun','node':'linux-169','task':{'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)},'bindings':{},'defaults':{},'secret_bindings':{'password':['workflow.0.what.0.args.1']},'checks':{'required_files':['Data/result.csv']}}
        validate(document);before=copy.deepcopy(document)
        task=bind_account(materialize(document,{}),document,{'password':'private-test-value'})
        self.assertEqual(task['secrets']['password'],'private-test-value')
        self.assertEqual(document,before);self.assertNotIn('private-test-value',str(document))
        document['bindings']={'password':['workflow.0.what.0.args.1']}
        with self.assertRaises(ValueError):validate(document)

    def test_public_binding_cannot_override_account_binding(self):
        source=robot();document={'engine':'maxun','node':'linux-169','task':{'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)},'bindings':{'x':['workflow.0.what.0.args.1']},'secret_bindings':{'password':['workflow.0.what.0.args.1']},'checks':{'required_files':['Data/result.csv']}}
        with self.assertRaises(ValueError):validate(document)
    def test_changed_published_workflow_never_starts(self):
        source=robot();task={'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)}
        source['recording']['workflow'][0]['what'][0]['args'][0]='#changed'
        client=FakeClient(source)
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(RuntimeError,'发生变化'):
            execute(task,{},Path(directory)/'run',client=client)
        self.assertFalse(client.started)

    def test_parameter_is_encrypted_and_source_unchanged(self):
        source=robot();before=copy.deepcopy(source)
        client=MaxunClient({'base_url':'http://localhost','api_key':'test','encryption_key':'01'*32})
        workflow=bind_inputs(source,{'begindate':['workflow.0.what.0.args.1']},{'begindate':'2026-11-12'},client)
        encrypted=workflow[0]['what'][0]['args'][1]
        self.assertNotIn('2026-11-12',encrypted);self.assertEqual(before,source)
        from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
        from cryptography.hazmat.primitives.padding import PKCS7
        iv,value=encrypted.split(':');dec=Cipher(algorithms.AES(bytes.fromhex('01'*32)),modes.CBC(bytes.fromhex(iv))).decryptor()
        padded=dec.update(bytes.fromhex(value))+dec.finalize();unpad=PKCS7(128).unpadder()
        self.assertEqual((unpad.update(padded)+unpad.finalize()).decode(),'2026-11-12')

    def test_cannot_bind_click_or_arbitrary_field(self):
        source=robot();source['recording']['workflow'][0]['what'][0]['action']='click'
        with self.assertRaises(ValueError):bind_inputs(source,{'x':['workflow.0.what.0.args.1']},{'x':'v'},None)
        with self.assertRaises(ValueError):bind_inputs(source,{'x':['__class__']},{'x':'v'},None)

    def test_success_without_required_file_is_failure(self):
        source=robot();task={'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)}
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(RuntimeError,'缺少成功产物'):
            execute(task,{'required_files':['Data/*.xlsx']},Path(directory)/'run',client=FakeClient(source))

    def test_structured_csv_uses_existing_business_checks(self):
        source=robot();task={'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)}
        output={'scrapeList':{'items':[{'商品':'测试商品','数量':'2'}]}}
        checks={'required_files':['Data/result.csv'],'min_rows':1,'required_columns':['商品','数量']}
        with tempfile.TemporaryDirectory() as directory:
            result=execute(task,checks,Path(directory)/'run',client=FakeClient(source,output=output))
            self.assertEqual(result['artifacts'][0]['row_count'],1)
            self.assertEqual(len(result['artifacts'][0]['sha256']),64)

    def test_maxun_only_on_enabled_linux_node(self):
        source=robot();document={'engine':'maxun','node':'windows-167','task':{'robot_id':source['recording_meta']['id'],'workflow_sha256':fingerprint(source)},'checks':{'required_files':['Data/result.csv']}}
        with self.assertRaises(ValueError):validate(document)
        document['node']='linux-169';validate(document)
        document.update(bindings={'begindate':['workflow.0.what.0.args.1']},defaults={'begindate':'2026-11-12'})
        before=copy.deepcopy(document)
        self.assertEqual(materialize(document,{})['parameters']['begindate'],'2026-11-12')
        self.assertEqual(document,before)
        with self.assertRaises(ValueError):materialize(document,{'extra':'value'})


if __name__=='__main__':unittest.main()
