# Mocha Debian 实机状态

以下是 r8 功能及其验证范围。系统下载见 [r8 整合包](https://github.com/Pisces-Moze/mocha-moze-flasher/releases/tag/source-candidate-20261121-r8)，剩余工作见 [任务表](TODO.md)。

| 功能 | 结果 | 验证范围 |
| --- | --- | --- |
| 内置双扬声器 | **已完成** | 左右声道听音、PipeWire 输出、受保护 TFA9890 功放及空闲断电已验证。r8 默认数字增益为 0 dB。耳机和麦克风另行验收。 |
| 前、后摄像头 | **已完成 V4L2 连续预览** | 两路均通过实机 RAM 取帧。前摄 640×360 约 15 fps、320×180 约 30 fps，后摄 1280×720 约 10 fps。一次使用一路，相机应用自行安装。详见 [双摄说明](https://github.com/Pisces-Moze/mocha-moze-drivers/blob/mocha-r8-sync-20261121/camera/README.md)。 |
| VDE 视频硬件解码 | **已完成已支持的 H.264 路径** | FFmpeg、GStreamer 逐帧校验通过，MPV 与 GOP30 动态壁纸已实际运行。当前实测范围是逐行 CAVLC，壁纸生命周期也已验证。详见 [播放器说明](https://github.com/Pisces-Moze/mocha-moze-desktop/blob/main/docs/VDE-PLAYER.md)。 |
| Firefox 网页视频 | **开发构建已硬解出帧** | 原型的独立 Request 构建使用 RDD／VDE，真实网站的编码覆盖与播放性能继续跟踪。预览整合包的浏览器能力以实际打包版本为准。[Firefox 验证](https://github.com/Pisces-Moze/mocha-moze-desktop/blob/mocha-r8-sync-20261121/docs/FIREFOX-RUNTIME.md) |
| 桌面、触控和充电 | **已有实机验收** | 原生 Tegra 双 DSI、Niri＋Noctalia、触控、充电动画及锁屏唤醒已在原型验证。 |
| Wi-Fi、蓝牙 | **已有实机验收** | Wi-Fi 连接、S102 音频、ThinkBook／K480 连接及输入节点已验证。 |
| 分区和安装 | **3 GiB APP 已验证** | 原型分区扩容、普通启动通过。r8 的 UDA 承载 /home。Windows 预览版的自动驱动绑定和较大容量实体机仍待单独验证。 |

[2026-10-07 状态快照](https://github.com/Pisces-Moze/mocha-moze-debian/blob/7b2bd69a1f76bd248985b5cfd1d20555df951acc/docs/STATUS.md)保留当时的结果。
