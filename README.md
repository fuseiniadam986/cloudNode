# CloudNode Panel

CloudNode Panel 是一个基于 Xray-core 的轻量级节点管理面板。当前版本为 `v0.3.0-beta`，目标是提供一个可以直接在 Debian/Ubuntu 服务器上一键部署的基础面板，并逐步补齐生产级协议编排、流量统计和升级维护能力。

> 声明：本项目仅供个人学习、研究和合法场景下的服务器管理使用。请遵守你所在地区的法律法规，严禁用于任何违法用途。

> 注意：当前版本仍是 Beta，不建议直接用于生产环境。请先在测试 VPS 上验证安装、访问、节点创建和 Xray 配置写入流程。

## 功能特性

- 后台登录，安装时自动生成随机初始密码
- 面板默认只监听 `127.0.0.1:8088`，避免直接暴露公网管理端口
- 节点列表、搜索、刷新
- 添加节点：节点名称、域名/IP、端口
- 编辑节点：名称、域名/IP、端口、启用状态
- 自动生成 UUID 和 XHTTP 路径
- 写入 Xray 配置前执行 `xray run -test`
- 创建失败自动撤销节点记录
- 删除节点
- 生成 VLESS + XHTTP 节点链接
- 生成节点二维码
- 生成统一订阅地址
- 查看面板、Xray、Caddy 日志
- 一键创建面板/Xray 配置备份
- 查看 Xray 服务状态
- 启动、停止、重启 Xray 服务
- systemd + Gunicorn 后台运行
- 自动检测并安装 Xray-core
- 可选启用 BBR
- 可选通过 Caddy 自动申请 HTTPS 证书并反代面板
- 提供状态、诊断、备份、卸载命令

## 当前限制

以下内容仍属于后续生产级增强，请不要把它们当成当前已完成能力：

- 节点协议层面的完整自动 TLS / REALITY 编排
- 完整系统优化菜单
- 流量统计
- 多协议一键生成
- 在线升级和回滚脚本
- 登录限速、CSRF、审计日志等后台加固

## 系统要求

- Debian 11+ / Ubuntu 20.04+
- root 权限
- systemd 环境

安装脚本会自动安装基础依赖；如果未检测到 Xray-core，会自动安装 Xray-core。

## 一键部署

无域名测试部署：

```bash
apt-get update && apt-get install -y git && rm -rf /tmp/cloudNode && git clone https://github.com/fuseiniadam986/cloudNode.git /tmp/cloudNode && bash /tmp/cloudNode/install.sh
```

有域名 HTTPS 部署：

```bash
apt-get update && apt-get install -y git && rm -rf /tmp/cloudNode && git clone https://github.com/fuseiniadam986/cloudNode.git /tmp/cloudNode && DOMAIN=panel.example.com EMAIL=admin@example.com bash /tmp/cloudNode/install.sh
```

启用 BBR：

```bash
ENABLE_BBR=1 bash /tmp/cloudNode/install.sh
```

也可以分步部署：

```bash
apt-get update && apt-get install -y git
git clone https://github.com/fuseiniadam986/cloudNode.git
cd cloudNode
bash install.sh
```

安装完成后，脚本会输出：

- 面板地址：`http://127.0.0.1:8088`
- 用户名：`admin`
- 随机初始密码

完整部署说明见：[docs/DEPLOY.md](docs/DEPLOY.md)。

## 访问面板

CloudNode Panel 默认只监听本机地址，不直接开放公网访问。推荐使用 SSH 隧道访问：

```bash
ssh -L 8088:127.0.0.1:8088 root@你的服务器IP
```

然后在本地浏览器打开：

```text
http://127.0.0.1:8088
```

如果你要通过域名访问，请自行配置受保护的 HTTPS 反向代理，不建议直接把 `8088` 管理端口暴露到公网。

如果安装时传入 `DOMAIN=你的域名`，脚本会使用 Caddy 自动配置 HTTPS 反代面板：

```bash
DOMAIN=panel.example.com EMAIL=admin@example.com bash install.sh
```

## 服务管理

查看面板状态：

```bash
systemctl status cloudnode-panel
```

重启面板：

```bash
systemctl restart cloudnode-panel
```

查看日志：

```bash
journalctl -u cloudnode-panel -f
```

查看 Xray 状态：

```bash
systemctl status xray
```

重启 Xray：

```bash
systemctl restart xray
```

安装器内置命令：

```bash
bash install.sh status
bash install.sh diagnose
bash install.sh backup
bash install.sh uninstall
```

## 安装位置

安装脚本会使用以下路径：

- 程序目录：`/opt/cloudnode-panel`
- 配置目录：`/etc/cloudnode-panel`
- 面板环境变量：`/etc/cloudnode-panel/env`
- 面板账号配置：`/etc/cloudnode-panel/panel.json`
- 节点状态文件：`/etc/cloudnode-panel/state.json`
- systemd 服务：`/etc/systemd/system/cloudnode-panel.service`
- Xray 配置：默认写入 `/usr/local/etc/xray/config.json`
- Caddy 配置：`/etc/caddy/Caddyfile`，仅在传入 `DOMAIN` 时生成

## 默认账号

默认用户名：

```text
admin
```

初始密码由安装脚本随机生成，只会在安装结束时显示。请妥善保存。

如果忘记密码，可以查看安装时生成的环境文件：

```bash
cat /etc/cloudnode-panel/env
```

当前 Beta 版本暂未提供网页修改密码功能。

## 安全提示

- 不要使用公网 HTTP 明文登录管理面板
- 推荐通过 SSH 隧道访问面板
- 如果要公网访问，请放在 HTTPS 反向代理后面
- 不要把 `/etc/cloudnode-panel/env`、`panel.json`、`state.json` 公开
- 当前版本会接管默认 Xray 配置文件，部署前请先备份原配置
- 不承诺“永不被封锁”或“速度一定更快”，实际效果取决于线路、机房、网络环境和客户端配置

备份 Xray 配置：

```bash
cp /usr/local/etc/xray/config.json /usr/local/etc/xray/config.json.bak
```

## 卸载

当前版本还没有正式卸载脚本。如需手动卸载：

```bash
bash install.sh uninstall
```

注意：这不会卸载 Xray-core，也不会恢复你原来的 Xray 配置。

## 版本状态

当前版本：`v0.3.0-beta`

这是第一阶段可运行 MVP，重点是验证：

- 面板安装
- 后台登录
- 节点创建
- 节点编辑
- 节点链接和二维码
- 订阅地址
- 日志和备份
- Xray 配置测试
- systemd 常驻运行

后续版本会继续补齐生产级 TLS/REALITY 编排、更多协议、流量统计和升级维护能力。

## License

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
