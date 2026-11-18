"""为既有部署手册补齐小屏表格与长路径换行，不修改业务内容。"""
from pathlib import Path
file=Path('doc/开发环境部署记录.html');text=file.read_text(encoding='utf-8')
style='@media(max-width:700px){body{overflow-wrap:anywhere}table{table-layout:fixed}td,th{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}}'
if style not in text:text=text.replace('</style>',style+'</style>',1)
file.write_text(text,encoding='utf-8')
