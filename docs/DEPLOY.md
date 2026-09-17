# CloudNode 部署指南

本文档用于服务器部署 CloudNode Panel Beta。

## 准备条件

- Debian 11+ 或 Ubuntu 20.04+
- root 权限
- 可访问 GitHub
- systemd 环境

如果需要 HTTPS 访问面板，请提前把域名 A 记录解析到服务器 IP，并开放 `80` 和 `443` 端口。

## 无域名部署

适合测试 VPS 或只想通过 SSH 隧道访问面板的场景。

```bash
apt-get update && apt-get install -y git && rm -rf /tmp/cloudNode && git clone https://github.com/fuseiniadam986/cloudNode.git /tmp/cloudNode && bash /tmp/cloudNode/install.sh
```

访问方式：

```bash
ssh -L 8088:127.0.0.1:8088 root@你的服务器IP
```

本地浏览器打开：

```text
http://127.0.0.1:8088
```

## 域名 HTTPS 部署

安装器会安装 Caddy，并自动申请和续期 TLS 证书。

```bash
apt-get update && apt-get install -y git && rm -rf /tmp/cloudNode && git clone https://github.com/fuseiniadam986/cloudNode.git /tmp/cloudNode && DOMAIN=panel.example.com EMAIL=admin@example.com bash /tmp/cloudNode/install.sh
```

部署完成后访问：

```text
https://panel.example.com
```

注意：

- `DOMAIN` 必须已经解析到当前服务器。
- 服务器安全组/防火墙需要放行 `80` 和 `443`。
- Caddy 这里只反代管理面板，不代表所有节点协议都已经自动 TLS 化。

## 启用 BBR

如果服务器内核支持 BBR，可以在安装时启用：

```bash
ENABLE_BBR=1 bash /tmp/cloudNode/install.sh
```

带域名一起使用：

```bash
DOMAIN=panel.example.com EMAIL=admin@example.com ENABLE_BBR=1 bash /tmp/cloudNode/install.sh
```

检查 BBR：

```bash
sysctl net.ipv4.tcp_congestion_control
```

## 管理命令

进入源码目录后执行：

```bash
bash install.sh status
bash install.sh diagnose
bash install.sh backup
bash install.sh uninstall
```

也可以直接使用 systemd：

```bash
systemctl status cloudnode-panel
systemctl restart cloudnode-panel
journalctl -u cloudnode-panel -f
```

## 重要限制

当前版本仍是 Beta：

- 不保证网络环境下的连通率。
- 不承诺“不会被封锁”或“速度一定更快”。
- 面板当前以基础节点创建和配置验证为主。
- 自动 HTTPS 主要覆盖管理面板访问，节点协议的完整 TLS/REALITY/多协议方案需要后续版本继续完善。

## 安全建议

- 优先通过 SSH 隧道访问面板。
- 如果公网访问面板，必须使用 HTTPS。
- 不要公开 `/etc/cloudnode-panel` 目录。
- 部署前备份原有 Xray 配置。
- 不要在生产服务器上直接测试未验证功能。
