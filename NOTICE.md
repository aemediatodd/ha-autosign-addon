# 来源说明

- 签到与推送逻辑来自 https://github.com/MikasaEureka/AutoSign-Bot-msg-Pusher ，基线提交 `b6d58d2`。原 README 署名/链接指向 https://github.com/clover1420/AutoSign ，已在 `UPSTREAM_README.md` 保留。
- 上游天翼云盘实现注明使用 https://github.com/xtyuns/cloud189app-action ，该说明保留在 `autosign/app/upstream/sign.py`。
- 小黑盒第三方签名接口及作者说明来自上游，**本适配未测试小黑盒，不保证接口仍有效**。
- 上游没有根目录许可证文件；本适配不为已有代码重新授权，不声明整个仓库为 MIT 或其他许可证。
- 不复制上游内置的 rsa/pyasn1 源码目录，改用 PyPI 的 rsa 及其依赖。Python、requests、rsa、pyasn1、Alpine 等组件遵循其各自许可证。
