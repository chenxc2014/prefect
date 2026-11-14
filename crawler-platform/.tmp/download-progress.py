"""只显示当前资源文件大小，不读取受限认证文件。"""
from pathlib import Path
for root in (Path('.local/designer'),Path('.local/browser-assets')):
    for file in root.glob('*'):
        print(file.name, file.stat().st_size)
