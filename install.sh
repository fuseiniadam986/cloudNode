#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[[ $EUID -eq 0 ]] || { echo "请使用 root 运行"; exit 1; }
. /etc/os-release
case "${ID:-}" in ubuntu|debian) ;; *) echo "Beta 仅支持 Debian/Ubuntu"; exit 1;; esac
command -v xray >/dev/null || { echo "未检测到 xray；请先安装 Xray-core。"; exit 1; }
apt-get update
apt-get install -y python3 python3-venv
install -d -m 0755 /opt/cloudnode-panel
cp -r app.py templates static /opt/cloudnode-panel/
python3 -m venv /opt/cloudnode-panel/.venv
/opt/cloudnode-panel/.venv/bin/pip install Flask gunicorn
PASS="$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
install -d -m 0700 /etc/cloudnode-panel
printf 'CLOUDNODE_PASSWORD=%s\nCLOUDNODE_SECRET=%s\n' "$PASS" "$SECRET" >/etc/cloudnode-panel/env
chmod 600 /etc/cloudnode-panel/env
cp systemd/cloudnode-panel.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now cloudnode-panel
echo
echo "CloudNode Panel Beta 已启动"
echo "地址: http://127.0.0.1:8088"
echo "用户名: admin"
echo "初始密码: $PASS"
echo "默认仅监听本机，不直接开放公网管理端口。"
