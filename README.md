# CloudNode Panel

CloudNode Panel 是一个基于 Xray-core 的轻量级节点管理面板。当前版本为 `v0.2.0-beta`，目标是先提供一个可安装、可登录、可创建基础节点的 MVP 面板，后续再逐步补齐多协议、订阅、证书、流量统计等能力。

> 声明：本项目仅供个人学习、研究和合法场景下的服务器管理使用。请遵守你所在地区的法律法规，严禁用于任何违法用途。

> 注意：当前版本仍是 Beta，不建议直接用于生产环境。请先在测试 VPS 上验证安装、访问、节点创建和 Xray 配置写入流程。

## 功能特性

- 后台登录，安装时自动生成随机初始密码
- 面板默认只监听 `127.0.0.1:8088`，避免直接暴露公网管理端口
- 节点列表、搜索、刷新
- 添加节点：节点名称、域名/IP、端口
- 自动生成 UUID 和 XHTTP 路径
- 写入 Xray 配置前执行 `xray run -test`
- 创建失败自动撤销节点记录
- 删除节点
- 查看 Xray 服务状态
- 启动、停止、重启 Xray 服务
- systemd + Gunicorn 后台运行

## 暂未实现

以下功能在 UI 规划中，但当前 Beta 版本还没有接入完整后端，请不要把它们当成已完成功能：

- 多协议一键生成
- 统一订阅链接和二维码
- 二维码刷新
- 自动 TLS / 证书申请
- BBR / 系统优化
- 流量统计
- 完整节点编辑弹窗
- 升级、备份、回滚脚本

## 系统要求

- Debian 11+ / Ubuntu 20.04+
- root 权限
- 已安装 Xray-core，并且系统中可以直接执行 `xray`
- systemd 环境

如果服务器还没有安装 Xray-core，请先安装 Xray，再部署 CloudNode Panel。

## 一键部署

在服务器复制粘贴执行：

```bash
apt-get update && apt-get install -y git && rm -rf /tmp/cloudNode && git clone https://github.com/fuseiniadam986/cloudNode.git /tmp/cloudNode && sudo bash /tmp/cloudNode/install.sh
```

也可以分步执行：

```bash
apt-get update && apt-get install -y git
git clone https://github.com/fuseiniadam986/cloudNode.git
cd cloudNode
sudo bash install.sh
```

安装完成后，脚本会输出：

- 面板地址：`http://127.0.0.1:8088`
- 用户名：`admin`
- 随机初始密码

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

## 安装位置

安装脚本会使用以下路径：

- 程序目录：`/opt/cloudnode-panel`
- 配置目录：`/etc/cloudnode-panel`
- 面板环境变量：`/etc/cloudnode-panel/env`
- 面板账号配置：`/etc/cloudnode-panel/panel.json`
- 节点状态文件：`/etc/cloudnode-panel/state.json`
- systemd 服务：`/etc/systemd/system/cloudnode-panel.service`
- Xray 配置：默认写入 `/usr/local/etc/xray/config.json`

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

备份 Xray 配置：

```bash
cp /usr/local/etc/xray/config.json /usr/local/etc/xray/config.json.bak
```

## 卸载

当前版本还没有正式卸载脚本。如需手动卸载：

```bash
systemctl disable --now cloudnode-panel
rm -f /etc/systemd/system/cloudnode-panel.service
systemctl daemon-reload
rm -rf /opt/cloudnode-panel
rm -rf /etc/cloudnode-panel
```

注意：这不会卸载 Xray-core，也不会恢复你原来的 Xray 配置。

## 版本状态

当前版本：`v0.2.0-beta`

这是第一阶段可运行 MVP，重点是验证：

- 面板安装
- 后台登录
- 节点创建
- Xray 配置测试
- systemd 常驻运行

后续版本会继续补齐订阅、证书、更多协议、流量统计和升级维护能力。

## License

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
