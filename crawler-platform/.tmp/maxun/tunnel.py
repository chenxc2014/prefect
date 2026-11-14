"""为内部验收转发 HTTPS，并为官方镜像下载提供临时开发机网络出口。"""
import importlib.util
from pathlib import Path
import select
import socket
import socketserver
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import getproxies

sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ssh',root/'.tmp/crawler-dev/manage.py')
ssh=importlib.util.module_from_spec(spec);spec.loader.exec_module(ssh)
transport=None

def relay(a,b):
    try:
        while True:
            ready,_,_=select.select([a,b],[],[],30)
            for source in ready:
                data=source.recv(65536)
                if not data:return
                (b if source is a else a).sendall(data)
    except (OSError,EOFError):
        pass
    finally:
        a.close();b.close()

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        target=transport.open_channel('direct-tcpip',('127.0.0.1',self.server.remote_port),self.request.getpeername())
        relay(self.request,target)

for local,remote in [(18443,8443),(19443,9443),(9443,9443),(18080,18080)]:
    server=socketserver.ThreadingTCPServer(('127.0.0.1',local),Handler,bind_and_activate=False)
    server.allow_reuse_address=True;server.daemon_threads=True;server.remote_port=remote
    server.server_bind();server.server_activate()
    threading.Thread(target=server.serve_forever,daemon=True).start()

proxy=urlsplit(getproxies().get('https',''))
if proxy.hostname not in ('127.0.0.1','localhost') or not proxy.port:
    raise RuntimeError('缺少本机现有网络代理，不创建任意外部出口')
print('内部验收隧道就绪：18443/19443/18080；临时下载出口仅绑定服务器回环地址',flush=True)
while True:
    client=None
    try:
        client=ssh.connect('169');transport=client.get_transport();transport.set_keepalive(10)
        transport.request_port_forward('127.0.0.1',28080)
        print('SSH 下载和验收隧道已连接',flush=True)
        while transport.is_active():
            channel=transport.accept(10)
            if channel:
                try:
                    sock=socket.create_connection((proxy.hostname,proxy.port),timeout=20)
                    threading.Thread(target=relay,args=(channel,sock),daemon=True).start()
                except OSError:
                    channel.close()
    except (OSError,EOFError) as error:
        print('临时隧道将重连：'+type(error).__name__,flush=True)
    finally:
        if client:client.close()
    time.sleep(2)
