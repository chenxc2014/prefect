"""验证文件日期和完整性判断，防止空文件或错误日期被当成成功。"""
from pathlib import Path
import tempfile
import unittest
from runtime.artifacts import validate_file


class ArtifactTest(unittest.TestCase):
    def test_business_date_and_required_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'result.csv'
            file.write_text('时间,商品编码,数量\n2026-11-12,P001,3\n',encoding='utf-8')
            checks={'date_columns':['时间'],'date_range':['2026-11-12','2026-11-12'],'required_columns':['商品编码','数量']}
            self.assertEqual(validate_file(file,checks)['row_count'],1)
            checks['date_range']=['2026-11-11','2026-11-11']
            with self.assertRaises(RuntimeError):validate_file(file,checks)

    def test_empty_and_missing_fields_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'result.csv'
            file.write_text('id,quantity\n',encoding='utf-8')
            with self.assertRaises(RuntimeError):validate_file(file,{'min_rows':1})
            file.write_text('id,quantity\n1,\n',encoding='utf-8')
            with self.assertRaises(RuntimeError):validate_file(file,{'required_columns':['quantity']})


if __name__=='__main__':unittest.main()
