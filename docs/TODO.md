# Mocha Debian 剩余任务

已完成的扬声器、前后摄 V4L2 连续预览，以及 FFmpeg／GStreamer／MPV／动态壁纸的 H.264 硬解，见 [实机状态](STATUS.md)。

| 优先级 | 待办 | 完成标准 |
| --- | --- | --- |
| P0 | Windows Flasher 预览包验收 | 在实际 Windows 设备上确认双击提权、原厂到 RAM Fastboot 的切换和自动修复驱动。对较大容量 Mocha 核对 GPT 及 APP 3 GiB、UDA 容量和冷启动。 |
| P1 | Firefox 网页视频性能 | 原型 Request 构建已硬解出帧。继续验证网站播放时的实际解码路径、帧率和 CPU／内存，将通过验收的构建纳入发行。 |
| P1 | 源码构建复现 | 在干净环境从固定源码完整构建并校验 r8 对应系统，记录实际与预构建包的差异。 |
| P2 | 外设能力扩展 | 耳机、麦克风、USB OTG、深度休眠及唤醒继续单独跟踪。相机高级控制与更多视频编码格式按支持能力验证。 |
| P2 | 持续性能 | 优化动态壁纸下的合成延迟、浏览器内存压力以及长时间播放时的调频和温控。 |
| P3 | 开放 CUDA 兼容扩展 | 保留已通过的计算、自检及有限运行时；完整官方 ABI 和高级功能继续按实际支持跟踪。 |

发行镜像直接进入桌面，OOBE 旧任务已结束。[历史任务记录](https://github.com/Pisces-Moze/mocha-moze-debian/blob/mocha-r8-sync-20261121/docs/TODO.md)保留开发过程。
