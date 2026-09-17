#!/usr/bin/env bash
set -euo pipefail

XRAY_CONFIG="${XRAY_CONFIG:-/usr/local/etc/xray/config.json}"
XRAY_SERVICE="${XRAY_SERVICE:-xray}"

die() { echo "cloudnode-helper: $*" >&2; exit 1; }
need_root() { [[ ${EUID:-$(id -u)} -eq 0 ]] || die "requires root"; }

apply_xray() {
  local src="${1:-}"
  [[ -n "$src" && -f "$src" ]] || die "missing generated config"
  local real
  real="$(realpath "$src")"
  [[ "$real" == /etc/cloudnode-panel/generated/*.json ]] || die "invalid config path"
  xray run -test -config "$real"
  install -m 0644 -o root -g root "$real" "$XRAY_CONFIG"
  systemctl restart "$XRAY_SERVICE"
}

service_xray() {
  local action="${1:-}"
  case "$action" in start|stop|restart) systemctl "$action" "$XRAY_SERVICE" ;; *) die "invalid service action" ;; esac
}

optimize_bbr() {
  cat >/etc/sysctl.d/99-cloudnode-bbr.conf <<'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
  sysctl --system
}

need_root
case "${1:-}" in
  apply-xray) apply_xray "${2:-}" ;;
  service-xray) service_xray "${2:-}" ;;
  optimize-bbr) optimize_bbr ;;
  *) die "usage: $0 {apply-xray FILE|service-xray start|stop|restart|optimize-bbr}" ;;
esac
