# 协作方式

提交时注明仓库 commit、内核 release、DT SHA256、冷启动还是 Fastboot 临时启动、实际屏幕观察及系统日志。
编译通过不能标成实机通过；DRM page flip 成功不能标成面板有图；有限 CUDA Driver API 自检不能标成完整 Runtime。
先用临时镜像验证，再讨论默认引导。不要提交设备密钥、Wi-Fi 密码、完整存储镜像、MAC 地址或未经许可的固件。
当前先处理原生显示和音频发现；CPU/GPU 调频、超频保持未启用。
