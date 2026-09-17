#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/cloudnode-panel"
ETC_DIR="/etc/cloudnode-panel"
SERVICE_FILE="/etc/systemd/system/cloudnode-panel.service"
HELPER_FILE="/usr/local/sbin/cloudnode-root-helper"
SUDOERS_FILE="/etc/sudoers.d/cloudnode-panel"
XRAY_CONFIG="${XRAY_CONFIG:-/usr/local/etc/xray/config.json}"
XRAY_SERVICE="${XRAY_SERVICE:-xray}"
DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-}"
ENABLE_BBR="${ENABLE_BBR:-0}"
REPO_URL="${REPO_URL:-https://github.com/fuseiniadam986/cloudNode.git}"

cd "$(dirname "$0")"

log() { echo "[CloudNode] $*"; }
die() { echo "[CloudNode] ERROR: $*" >&2; exit 1; }

require_root() {
  [[ ${EUID:-$(id -u)} -eq 0 ]] || die "请使用 root 运行"
}

check_os() {
  . /etc/os-release
  case "${ID:-}" in
    ubuntu|debian) ;;
    *) die "当前 Beta 仅支持 Debian/Ubuntu" ;;
  esac
}

install_base_packages() {
  apt-get update
  apt-get install -y curl ca-certificates python3 python3-venv iproute2 sudo
}

install_xray_if_missing() {
  if command -v xray >/dev/null 2>&1; then
    log "检测到 Xray: $(command -v xray)"
    return
  fi

  log "未检测到 Xray，开始安装 Xray-core"
  bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
}

enable_bbr_if_requested() {
  [[ "$ENABLE_BBR" == "1" ]] || return

  log "启用 BBR 网络拥塞控制"
  cat >/etc/sysctl.d/99-cloudnode-bbr.conf <<'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
  sysctl --system >/dev/null || true
  sysctl net.ipv4.tcp_congestion_control || true
}

backup_xray_config() {
  if [[ -f "$XRAY_CONFIG" ]]; then
    local bak="${XRAY_CONFIG}.cloudnode.$(date +%Y%m%d%H%M%S).bak"
    cp "$XRAY_CONFIG" "$bak"
    log "已备份 Xray 配置: $bak"
  fi
}

install_panel() {
  log "部署 CloudNode Panel 到 $APP_DIR"
  if ! id -u cloudnode >/dev/null 2>&1; then
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin cloudnode
  fi
  install -d -m 0755 "$APP_DIR"
  cp -r app.py templates static "$APP_DIR/"

  python3 -m venv "$APP_DIR/.venv"
  "$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
  "$APP_DIR/.venv/bin/pip" install Flask gunicorn qrcode

  install -d -m 0750 -o cloudnode -g cloudnode "$ETC_DIR"
  install -d -m 0700 -o cloudnode -g cloudnode "$ETC_DIR/generated"
  local pass secret
  if [[ -f "$ETC_DIR/env" ]]; then
    # shellcheck disable=SC1091
    . "$ETC_DIR/env"
    pass="${CLOUDNODE_PASSWORD:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')}"
    secret="${CLOUDNODE_SECRET:-$(python3 -c 'import secrets;print(secrets.token_hex(32))')}"
  else
    pass="$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')"
    secret="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  fi
  {
    printf 'CLOUDNODE_PASSWORD=%q\n' "$pass"
    printf 'CLOUDNODE_SECRET=%q\n' "$secret"
    printf 'XRAY_CONFIG=%q\n' "$XRAY_CONFIG"
    printf 'XRAY_SERVICE=%q\n' "$XRAY_SERVICE"
    printf 'XRAY_API_PORT=%q\n' "10085"
    printf 'CLOUDNODE_HELPER=%q\n' "$HELPER_FILE"
  } >"$ETC_DIR/env"
  chown cloudnode:cloudnode "$ETC_DIR/env"
  chmod 600 "$ETC_DIR/env"

  install -m 0750 -o root -g root scripts/cloudnode-root-helper.sh "$HELPER_FILE"
  cat >"$SUDOERS_FILE" <<EOF
cloudnode ALL=(root) NOPASSWD: $HELPER_FILE *
EOF
  chmod 0440 "$SUDOERS_FILE"
  visudo -cf "$SUDOERS_FILE" >/dev/null

  cp systemd/cloudnode-panel.service "$SERVICE_FILE"
  chown -R cloudnode:cloudnode "$APP_DIR"
  systemctl daemon-reload
  systemctl enable --now cloudnode-panel

  echo
  echo "CloudNode Panel Beta 已启动"
  echo "面板地址: http://127.0.0.1:8088"
  echo "用户名: admin"
  echo "初始密码: $pass"
}

install_caddy_if_domain_set() {
  [[ -n "$DOMAIN" ]] || return

  log "检测到 DOMAIN=$DOMAIN，开始配置 Caddy HTTPS 反向代理"
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https gpg
  install -d -m 0755 /usr/share/keyrings
  rm -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update
  apt-get install -y caddy

  local email_line=""
  [[ -n "$EMAIL" ]] && email_line="email $EMAIL"
  cat >/etc/caddy/Caddyfile <<EOF
{
    $email_line
}

$DOMAIN {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8088
}
EOF

  systemctl enable --now caddy
  systemctl reload caddy
  echo "HTTPS 面板地址: https://$DOMAIN"
}

status() {
  systemctl --no-pager status cloudnode-panel || true
  systemctl --no-pager status "$XRAY_SERVICE" || true
  if command -v caddy >/dev/null 2>&1; then
    systemctl --no-pager status caddy || true
  fi
}

backup() {
  local out="/root/cloudnode-backup-$(date +%Y%m%d%H%M%S).tar.gz"
  tar -czf "$out" "$ETC_DIR" "$APP_DIR" "$SERVICE_FILE" "$HELPER_FILE" "$SUDOERS_FILE" 2>/dev/null || true
  echo "$out"
}

update_self() {
  local tmp="/tmp/cloudNode-update"
  rm -rf "$tmp"
  apt-get update
  apt-get install -y git
  git clone "$REPO_URL" "$tmp"
  [[ -f "$tmp/install.sh" && -f "$tmp/app.py" && -f "$tmp/scripts/cloudnode-root-helper.sh" ]] || die "更新包不完整"
  bash "$tmp/install.sh"
}

rollback() {
  local file="${1:-}"
  [[ -n "$file" && -f "$file" ]] || die "用法: bash install.sh rollback /root/cloudnode-backup-xxxx.tar.gz"
  local real
  real="$(realpath "$file")"
  [[ "$real" == /root/cloudnode-backup-*.tar.gz || "$real" == "$ETC_DIR"/backup-*.tar.gz ]] || die "只允许回滚 CloudNode 生成的备份文件"
  if tar -tzf "$real" | grep -Ev '^(etc/cloudnode-panel/|opt/cloudnode-panel/|etc/systemd/system/cloudnode-panel\.service$|usr/local/sbin/cloudnode-root-helper$|etc/sudoers.d/cloudnode-panel$)' >/dev/null; then
    die "备份内容包含非 CloudNode 路径，拒绝回滚"
  fi
  systemctl stop cloudnode-panel 2>/dev/null || true
  tar -xzf "$real" -C /
  systemctl daemon-reload
  systemctl enable --now cloudnode-panel
  log "已从备份恢复: $real"
}

diagnose() {
  echo "== OS =="
  cat /etc/os-release || true
  echo
  echo "== Ports =="
  ss -lntup | grep -E '(:8088|:80|:443)' || true
  echo
  echo "== Services =="
  systemctl is-active cloudnode-panel || true
  systemctl is-active "$XRAY_SERVICE" || true
  systemctl is-active caddy || true
  echo
  echo "== Xray test =="
  if command -v xray >/dev/null 2>&1 && [[ -f "$XRAY_CONFIG" ]]; then
    xray run -test -config "$XRAY_CONFIG" || true
  else
    echo "xray 或配置文件不存在"
  fi
}

uninstall() {
  echo "即将卸载 CloudNode Panel，不会卸载 Xray-core。"
  read -r -p "请输入 YES 确认卸载: " ans
  [[ "$ans" == "YES" ]] || die "已取消"
  systemctl disable --now cloudnode-panel 2>/dev/null || true
  rm -f "$SERVICE_FILE"
  rm -f "$HELPER_FILE" "$SUDOERS_FILE"
  systemctl daemon-reload
  rm -rf "$APP_DIR" "$ETC_DIR"
  log "已卸载 CloudNode Panel"
}

install_all() {
  require_root
  check_os
  install_base_packages
  install_xray_if_missing
  enable_bbr_if_requested
  backup_xray_config
  install_panel
  install_caddy_if_domain_set

  echo
  echo "常用命令:"
  echo "  bash install.sh status"
  echo "  bash install.sh diagnose"
  echo "  bash install.sh backup"
  echo "  bash install.sh update"
  echo "  bash install.sh rollback /root/cloudnode-backup-xxxx.tar.gz"
  echo "  bash install.sh uninstall"
}

case "${1:-install}" in
  install) install_all ;;
  status) require_root; status ;;
  backup) require_root; backup ;;
  update) require_root; update_self ;;
  rollback) require_root; rollback "${2:-}" ;;
  diagnose) require_root; diagnose ;;
  uninstall) require_root; uninstall ;;
  *) die "用法: bash install.sh [install|status|backup|update|rollback|diagnose|uninstall]" ;;
esac
