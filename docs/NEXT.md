# 下一阶段

## 已补齐的部署基础

1. 安装脚本自动安装基础依赖
2. 未检测到 Xray 时自动安装 Xray-core
3. 可选 `ENABLE_BBR=1` 启用 BBR
4. 可选 `DOMAIN` + `EMAIL` 安装 Caddy 并自动申请 HTTPS 证书
5. 提供 `status`、`diagnose`、`backup`、`uninstall` 命令
6. README 与部署文档补齐公开项目说明

## 下一阶段功能

1. 节点编辑弹窗
2. 节点协议层面的 TLS / REALITY / XHTTP 完整编排
3. BBR 状态在面板内展示
4. 分享配置页面
5. QR 生成
6. 统一订阅端点
7. 多协议适配，逐项实机验证后启用
8. 日志页与备份恢复
9. CSRF、登录限速、审计日志等后台加固
10. 升级回滚流程
