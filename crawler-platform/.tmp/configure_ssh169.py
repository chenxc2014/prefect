import base64
import getpass
import hashlib
from pathlib import Path
import shlex
import subprocess
import paramiko

HOST = '192.168.1.169'
KEY = Path(r'C:\Users\chenx\.ssh\id_ed25519_chenxc')
PUB = KEY.with_suffix('.pub').read_text(encoding='utf-8-sig').strip()
private = paramiko.Ed25519Key.from_private_key_file(str(KEY))
assert private.get_base64() == PUB.split()[1], '公私钥不匹配'
client = paramiko.SSHClient()
client.load_system_host_keys(str(KEY.parent / 'known_hosts'))
client.set_missing_host_key_policy(paramiko.WarningPolicy())
client.connect(HOST, port=22, username='root', password=getpass.getpass('服务器密码: '), look_for_keys=False, allow_agent=False, timeout=15)
hostkey = client.get_transport().get_remote_server_key()
print('HOST_FINGERPRINT SHA256:' + base64.b64encode(hashlib.sha256(hostkey.asbytes()).digest()).decode().rstrip('='), flush=True)

def run(command):
    stdin, stdout, stderr = client.exec_command(command, timeout=45)
    out, err = stdout.read().decode(), stderr.read().decode()
    print(out, end='', flush=True)
    print(err, end='', flush=True)
    code = stdout.channel.recv_exit_status()
    if code:
        raise RuntimeError(f'远程命令失败: {code}')

run('''set -e
cat /etc/rocky-release
systemctl is-active sshd
systemctl is-enabled sshd
printf '\\n--- 生效配置 ---\\n'
/usr/sbin/sshd -T -C user=root,host=$(hostname),addr=${SSH_CLIENT%% *} | grep -E '^(port|pubkeyauthentication|passwordauthentication|permitrootlogin|authorizedkeysfile|allowtcpforwarding|gatewayports|clientalive|authenticationmethods|pubkeyacceptedalgorithms|allowusers|denyusers|allowgroups|denygroups) '
printf '\\n--- 配置文件 ---\\n'
grep -nEv '^[[:space:]]*(#|$)' /etc/ssh/sshd_config
find /etc/ssh/sshd_config.d -maxdepth 1 -type f -name '*.conf' -print -exec cat {} \\;
printf '\\n--- 权限与防火墙 ---\\n'
ls -ld /root /root/.ssh 2>/dev/null || true
ls -lZ /root/.ssh/authorized_keys 2>/dev/null || true
getenforce
update-crypto-policies --show
passwd -S root
if systemctl is-active --quiet firewalld; then firewall-cmd --get-active-zones; firewall-cmd --list-all; firewall-cmd --permanent --list-all; fi
''')
if input('输入 APPLY 执行配置: ').strip() != 'APPLY':
    client.close()
    raise SystemExit('已取消')

run('''set -eu
backup=/root/ssh-backup-$(date +%Y%m%d-%H%M%S)
install -d -m 700 "$backup"
cp -a /etc/ssh/sshd_config "$backup/"
cp -a /etc/ssh/sshd_config.d "$backup/"
if [ -f /root/.ssh/authorized_keys ]; then cp -a /root/.ssh/authorized_keys "$backup/authorized_keys"; fi
echo "BACKUP=$backup"
install -d -m 700 -o root -g root /root/.ssh
touch /root/.ssh/authorized_keys
'''+ f'key={shlex.quote(PUB)}\n'+'''
if ! grep -qF "$(printf '%s' "$key" | awk '{print $2}')" /root/.ssh/authorized_keys; then
    printf '\\n%s\\n' "$key" >> /root/.ssh/authorized_keys
fi
chown root:root /root/.ssh /root/.ssh/authorized_keys
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
restorecon -Rv /root/.ssh
cat > /etc/ssh/sshd_config.d/10-keyauth.conf <<'EOF'
# 公钥免密访问配置，保留现有密码登录通道
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
AllowTcpForwarding yes
GatewayPorts no
ClientAliveInterval 60
ClientAliveCountMax 3
PermitRootLogin yes
PasswordAuthentication yes
PermitEmptyPasswords no
EOF
chmod 600 /etc/ssh/sshd_config.d/10-keyauth.conf
if ! /usr/sbin/sshd -t; then
    if [ -f "$backup/sshd_config.d/10-keyauth.conf" ]; then cp -a "$backup/sshd_config.d/10-keyauth.conf" /etc/ssh/sshd_config.d/10-keyauth.conf; else rm -f /etc/ssh/sshd_config.d/10-keyauth.conf; fi
    exit 1
fi
systemctl reload sshd
/usr/sbin/sshd -T -C user=root,host=$(hostname),addr=${SSH_CLIENT%% *} | grep -E '^(pubkeyauthentication|passwordauthentication|permitrootlogin|authorizedkeysfile|allowtcpforwarding|gatewayports|clientaliveinterval|clientalivecountmax) '
ls -ld /root/.ssh
ls -lZ /root/.ssh/authorized_keys
ssh-keygen -lf /root/.ssh/authorized_keys
systemctl is-active sshd
''')

# 使用独立新连接验证仅凭指定私钥登录。
test = paramiko.SSHClient()
test.get_host_keys().add(HOST, hostkey.get_name(), hostkey)
test.connect(HOST, username='root', pkey=private, look_for_keys=False, allow_agent=False, timeout=15)
stdin, stdout, stderr = test.exec_command('id; hostname')
print('PUBLICKEY_LOGIN_OK', stdout.read().decode(), flush=True)
test.close()
known = Path(__file__).with_name('ssh169_known_hosts')
known.write_text(f'{HOST} {hostkey.get_name()} {hostkey.get_base64()}\n', encoding='ascii')
result = subprocess.run(['ssh', '-v', '-p', '22', '-i', str(KEY), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'PreferredAuthentications=publickey', '-o', 'PasswordAuthentication=no', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known.resolve()), 'root@' + HOST, 'id; hostname'], capture_output=True, text=True, timeout=30)
print(result.stdout)
print('\n'.join(line for line in result.stderr.splitlines() if 'Authenticated' in line or 'Server accepts key' in line or 'WARNING' in line))
assert result.returncode == 0, result.stderr
print('WINDOWS_OPENSSH_BATCH_LOGIN_OK', flush=True)
run("journalctl -u sshd --since '5 minutes ago' --no-pager | grep 'Accepted publickey' | tail -4")
client.close()
