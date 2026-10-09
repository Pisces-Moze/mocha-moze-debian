# 2026-10-10 RAM 引导与原生显示诊断

本轮从原厂 Fastboot 临时加载新 RAM U-Boot，再分别启动新 stable/native 内核。没有写 APP/LNX 或更改默认引导；eMMC 全盘保持只读。**两套内核实际 ELF core 捕获通过，native 面板输出仍黑屏。**

| 实机检查 | 结果 | 证据与范围 |
|---|---|---|
| RAM U-Boot | 用户确认画面正常，显示 `Mocha RAM USB diagnostics`；USB 产品、版本、RAM 上传和 bootm 成功 | [引导记录](diagnostics/2026-10-10-uboot-ram-runtime.json)；不是默认冷启动或刷机验收 |
| stable RAM 内核 | `6.12.111-moze.1`，四核在线，用户确认 Linux 日志正常 | [stable core](diagnostics/2026-10-10-stable-ram-core.json) |
| native RAM 内核 | `6.12.111-moze.1-native`，四核在线、USB SSH 可用，屏幕黑 | [native core](diagnostics/2026-10-10-native-ram-core.json) |
| 实际 core | 两个内核的三个 core 选项均为 y；受控 SIGSEGV 返回 139，各生成 327680 字节 ELF32/ET_CORE/EM_ARM 文件 | 文件位于 RAM `/tmp`，限制 4 MiB；保存头部、大小和 SHA256，未发布原始 core；捕获时未挂载 eMMC |
| native 背光模块 | vermagic 匹配；insmod 返回 0，背光设备注册；DSI 从 disconnected 变成 connected/enabled，建立 tegradrmfb | [显示记录](diagnostics/2026-10-10-native-display.json)；背光亮不等于面板有图像 |
| 候选 Mesa fence | Nouveau、强制 Tegra 包装层、真实 Tegra `renderD128` 三组各通过 32 轮 fence/共享纹理像素检查 | [EGL 输出](diagnostics/2026-10-10-native-mesa-egl.json)；实际 EGL Mesa/GBM/Gallium 均来自候选目录；这项没有 modeset |
| DRM 驱动识别 | libdrm 返回 `tegra`，sysfs host1x 驱动目录名实际为 `drm` | 修正探针用 `drmGetVersion` 检查 ABI 名称；仍以退出码 1 拒绝 Nouveau |
| CPU framebuffer 色块 | 1536×2048、XR24、pitch 6144；程序完成并恢复 framebuffer | 用户两次确认背光亮但黑屏 |
| GPU DMA-BUF / native KMS 色块 | 线性 buffer 导出/导入成功、1800 次翻页、60.018 秒、29.99 FPS、程序内 CPU 像素复制次数 0 | 用户确认背光亮但黑屏；不能据此宣称扫描输出、zero-copy 或原生桌面通过；测试结束恢复原 CRTC |

GPU 测试使用 `native-dmabuf-scanout-v2.c` 的私有 RAM 诊断变体，仅把旧 debug4 引导参数门禁换为当前 RAM 的 `rdinit=/init`，并把运行时长从 5 秒改为 60 秒。源文件与二进制 SHA256 均在显示记录中；不能称为原公开程序未经修改的测试。

进行 Mesa/GPU 测试时，APP 与数据分区挂载为 `ro,noload`，从已有安装读取 ARM 用户态、候选 Mesa 和固件；`/tmp`、设备节点与运行目录仍在 RAM。没有替换系统 Mesa，没有启动 Niri，没有加载音频实验模块，也没有调整充电限流。

此前 stock Fastboot 的 bulk 写超时在拔掉 USB 并完全冷关机后消失。stock 和 RAM U-Boot 各有独立的 Windows USB 实例，都已绑定签名 WinUSB 驱动；ADB 工具安装本身不能替代这个绑定。软件重启到 bootloader 曾进入 APX，后续继续使用电源＋音量减手动进入原厂 Fastboot。

目前故障范围已缩小：CPU 绘制和 GPU 绘制均黑屏，DRM active、翻页回调和 fence 成功不足以证明物理输出。当前 DSI/面板源码与原先构建主机保存的源码相同，公开 native DTS 沿用 native6 的主从链路；历史可见色块来自 native5。下一步只在 RAM 对照 native5 链路顺序，保持内核、initrd 和 12 MHz DSI LP 时钟不变。对照 DTB 已编译校验，尚未执行，默认 DTS 保持不变。

完整改名后安装、原生 Niri 画面、控制台布局、音频、蓝牙完整功能、DVFS 和休眠仍未完成。`new_brand_end_to_end_tested` 继续为 false。
