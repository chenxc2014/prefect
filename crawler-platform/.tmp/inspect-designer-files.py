"""定位已安装客户端入口，不启动交互窗口。"""
from pathlib import Path
for path in Path('.local/designer').rglob('EasySpider.exe'):
    print(path.resolve())
