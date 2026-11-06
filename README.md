# AutoSign Home Assistant add-on

将 [AutoSign-Bot-msg-Pusher](https://github.com/MikasaEureka/AutoSign-Bot-msg-Pusher) 适配为 Home Assistant OS / Supervised 加载项（新版本 HA 称为“应用”）。提供中文 Ingress 页面、每日计划、按平台手动签到，以及原项目的 Qmsg、Server 酱、企业微信、钉钉推送。

**小黑盒未测试，默认关闭，不保证可用。其他平台的真实账户验证状态见 [验证报告](VALIDATION.md)，不能将容器启动成功视为签到验证成功。**

## 安装

1. HA → 设置 → 应用（或加载项）→ 应用商店 → 右上角菜单 → 仓库，添加：
   `https://github.com/aemediatodd/ha-autosign-addon`
2. 找到 **AutoSign 自动签到**，安装并启动。使用 GitHub Actions 构建的 GHCR 多架构镜像，HA 端需能访问 `ghcr.io`，无需本地构建或直接连接 Docker Hub。
3. 点击“打开网页界面”。所有平台和每日定时默认关闭；填写所需平台凭据、启用该平台并保存。
4. 点击该平台的“仅测试此平台”，检查结果。按钮会执行真实登录和签到。
5. 设置时间和时区，打开每日定时，保存即可。可在应用信息页按需开启“开机启动”。

填写或修改账户后立即生效，无需重启 HA 或加载项。支持 amd64、aarch64；实际构建验证范围见验证报告。仓库维护者首次发布后需在 GitHub Packages 设置中将 `ha-autosign-addon` 包设为 Public，才能匿名安装。

## 账户配置

| 平台 | 必填内容 | 说明 |
| --- | --- | --- |
| MIUI 历史版本 | 账号、密码 | 自动登录取得 Cookie 后签到 |
| 好游快爆 | 完整签到表单请求体 | 来自 `huodong3.3839.com/n/hykb/cornfarm/ajax_sign.php`，包含 `ac=Sign`、登录与设备参数；沿用上游字段名 cookie，但不是 HTTP Cookie 头。旧 grow 接口已跳转，需重新抓取新版请求 |
| 交易猫 | Cookie | 如站点需要 CSRF，Cookie 中应含当前 `_csrfToken`；已移除原代码的固定 CSRF 值 |
| 天翼云盘 | 账号、密码 | 登录可能受验证码、风控或上游接口变化影响；不自动绕过验证码 |
| 网易云游戏 | Authorization 值 | 在官网登录后，从开发者工具请求头获取完整值 |
| 小黑盒 | Cookie，IMEI 可选 | **未测试**；沿用旧版接口与第三方 HTTP 签名服务 |

平台凭据请在本地 HA 页面填写。不要将凭据放入 GitHub Issue、截图或仓库。密码、Cookie 和推送密钥保存在加载项私有 `/data/config.json`，HA 备份可能包含该文件。页面由 HA Ingress 鉴权，未开放宿主机端口，不需要 HA API、Supervisor API、主机网络或特权权限。

## 定时与手动执行

- 默认时区 `Asia/Hong_Kong`，默认计划时间 `07:00`，定时开关默认关闭。
- 定时每天最多执行一次；当日超过指定时间后启动或启用计划，会补执行当日任务。
- 执行记录持久化，避免正常重启后重复自动签到。为避免崩溃时重复提交，会在运行前记录当日计划已触发；中途崩溃需手动检查并执行。
- 手动执行可以重复触发；任务运行期间拒绝重复启动或修改配置。只执行已启用的平台。
- 各平台分别处理异常，一个平台失败会继续下一个。HTTP 有连接/读取超时，不自动重试签到请求。
- 推送和签到结果分别显示；推送失败不会将签到结果改为成功。
- Cookie 过期或接口变化需要更新配置。上游已有平台接口可能失效，兼容代码不代表平台可用承诺。

## 本地开发

```shell
python -m pip install requests==2.32.5 rsa==4.9.1 pytest tzdata
python -m pytest -q
```

有其他项目 pytest 插件干扰时，设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` 后再运行。测试使用模拟请求，不使用真实账户，也不调用小黑盒接口。Linux 上可设置 `AUTOSIGN_DATA` 指向空目录，再运行 `python autosign/app/server.py`，从本机 `http://127.0.0.1:8099` 调试。

## 来源与改动

基于上游提交 `b6d58d2` 的签到和推送实现，保留相关来源说明；原说明存放于 [UPSTREAM_README.md](UPSTREAM_README.md)。此适配新增了 HA 加载项封装、Ingress 配置页、调度、持久化、超时、错误隔离和测试，并修复 MIUI 登录 Cookie 判断、天翼登录失败后继续签到及推送错误报告等问题。0.1.1 根据当前公开登录流程更新天翼云盘登录协议与好游快爆玉米农场签到接口；真实账户验证范围仍以验证报告为准。

上游仓库未提供根目录 LICENSE，本仓库不为上游代码另行声明许可证。第三方来源与范围见 [NOTICE.md](NOTICE.md)。
