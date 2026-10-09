# 2026-10-10 RAM 引导与原生显示诊断

本轮从原厂 Fastboot 临时加载新 RAM U-Boot，再分别启动新 stable/native 内核。没有写 APP/LNX 或更改默认引导；eMMC 全盘保持只读。**两套内核实际 ELF core 捕获通过；native 首轮黑屏，恢复面板控制主机并单独校正扫描起点后，用户确认 CPU 色块位置正常。原始内核配合手动校正的 GPU 色块和 Niri＋终端已由用户确认正常；两版旧自动方案失败；主动模块复位候选后续通过自动 CPU/GPU/Niri 及第二次冷 RAM CPU/控制台验收，仍未默认化。**

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

进行 Mesa/GPU 测试时，APP 与数据分区挂载为 `ro,noload`，从已有安装读取 ARM 用户态、候选 Mesa 和固件；`/tmp`、设备节点与运行目录仍在 RAM。没有替换系统 Mesa，首轮未启动 Niri；后续独立 Niri 验证见下文，没有加载音频实验模块，也没有调整充电限流。

此前 stock Fastboot 的 bulk 写超时在拔掉 USB 并完全冷关机后消失。stock 和 RAM U-Boot 各有独立的 Windows USB 实例，都已绑定签名 WinUSB 驱动；ADB 工具安装本身不能替代这个绑定。软件重启到 bootloader 曾进入 APX，后续继续使用电源＋音量减手动进入原厂 Fastboot。

首轮故障范围：CPU 绘制和 GPU 绘制均黑屏，DRM active、翻页回调和 fence 成功不足以证明物理输出。DSI/面板源码与原先构建主机保存的源码相同，公开 native DTS 沿用 native6 的主从链路；历史可见色块来自 native5。

随后保持内核、initrd 和 12 MHz DSI LP 时钟不变，仅在 RAM 恢复 native5 链路顺序。用户确认色块可见，但左右交换、日志从中间开始；原始起点为 DSI-A=768、DSI-B=0。继续保留 DSI-B 主机／面板资源归属，只把两个 `DSI_GANGED_MODE_START` 改为 A=0、B=768，用户确认四象限位置正常。诊断程序结束恢复 framebuffer 和原始寄存器，后续为便于观察控制台再次在 RAM 应用正确起点；没有更改时钟、电源或默认引导。详见 [链路对照](diagnostics/2026-10-10-native-link-comparison.json)。

代码修复保留可工作的 DSI-B 控制主机，增加本地绑定 `nvidia,ganged-mode-swap-links`，让主从控制关系与横向扫描半屏独立设置。缺省属性保持原有行为，stable DTS 不变。恢复 native5 后，修正 libdrm ABI 字段类型的探针也再次通过三组各 32 轮 EGL 回归，并正确拒绝 Nouveau：见 [复核输出](diagnostics/2026-10-10-native5-mesa-egl.json)。

第一版自动分段内核完整构建并 RAM 启动，寄存器自动为 A=0、B=768，但用户确认仍黑屏；再次切换运行时起点也不能恢复。它是在面板 prepare 之后、视频 enable 之前改变分段，与前一次成功的运行时修正时机不同，不能据寄存器值标记修复通过。该版 core 再次捕获成功，完整负面记录见 [首版自动布局](diagnostics/2026-10-10-native-auto-layout-initial.json)。后续候选保留原始分段启动两路视频，再等待 40 ms 后仅校正扫描起点；完整构建已通过，RAM 启动和 core 捕获也通过，但用户再次确认背光亮、黑屏；A=0、B=768 自动设置正确，未手动写起点。40 ms 延后方案也不能标为修复，见 [第二版自动布局](diagnostics/2026-10-10-native-auto-layout-late.json)。随后保持这个新内核，使用此前可显示的 native5 DTB 并关闭自动校正，A=768/B=0，但用户仍确认背光亮、黑屏。该 [同内核对照](diagnostics/2026-10-10-native5-new-kernel.json) 表明自动起点写入不是唯一解释；重新启动此前可显示的原始内核＋native5 DTB 后，用户再次确认色块可见，live DT 哈希也与首次成功相同，见 [原始组合复测](diagnostics/2026-10-10-native5-baseline-repeat.json)。随后完成原始 DSI 源码重建，并进一步做了同次启动的 DPMS 对照，结果见下文。

在可显示的原始内核＋native5 DTB 中，手动校正 A=0/B=768 后，GPU 线性 DMA-BUF/KMS 色块完成 1785 帧、60.018 秒、29.74 FPS，程序内 CPU 像素复制调用为 0，用户确认可见且位置正常，详见 [GPU 实测](diagnostics/2026-10-10-native5-gpu-scanout.json)。随后用候选 Mesa 启动已安装的 Niri 26.04＋foot，真实 Tegra renderD128、card1/DSI-1 输出，用户确认蓝色背景与终端完全正常。Niri 实际映射的 EGL Mesa、GBM、Gallium 路径及 SHA256 已核对；native KMS plane 为线性 XR24、pitch 6144、DMA-BUF imported。Niri modeset 重新设置原始分段后，仍需手动校正 A=0/B=768。180 秒限时会话收到预期 SIGTERM，未见 SIGSEGV/core；SSH TTY 启动器返回 1，未验证 Niri 本身的干净退出码。见 [Niri 实测](diagnostics/2026-10-10-native5-niri.json)。

这是既有 Niri 二进制与候选 Mesa 的独立 RAM 验证，Niri 源码 commit 未确认；未覆盖 Noctalia 全会话、触控、长期运行、自动分段或改名后的完整安装。block-linear TEST_ONLY 仍返回 EINVAL，本次使用现有线性回退，不代表该格式兼容问题修复。

原始 DSI 源码在已有 native 输出目录重建后，首次 CPU/GPU 色块仍黑屏。逐字节对照两个 23715220 字节内核 payload，只有 34 字节不同，分别属于 `linux_banner`、`init_uts_ns` 的构建号/时间字符串和 GNU Build ID；机器指令相同。保持这次启动与原始 A=768/B=0 分段不变，通过 DRM DPMS OFF→ON 执行既有的关闭/开启路径，两次调用均返回 0，用户确认四色恢复但左右交换。随后仅手动设置 A=0/B=768，GPU 测试完成 1801 帧／60.001 秒／30.02 FPS，程序内 CPU 像素复制调用为 0，用户确认位置正确。这次重建基线上，候选 Mesa 下的 Niri＋更新终端也由用户确认正常，180 秒限时结束时收到 SIGTERM，未见新的 SIGSEGV/core；实际进程映射的三类候选库与 SHA256 已核对。Niri modeset 后仍需手动校正分段，干净退出码未确认。详见 [重建基线与 DPMS 对照](diagnostics/2026-10-10-native-baseline-dpms.json)。该结果支持首次初始化状态/时序的排查方向，不能归因于编译器生成不同机器指令，也没有单独证明 DSI 复位就是根因。当前候选仅在 Mocha 的 DSI runtime resume 中，于主/低功耗时钟就绪后主动 assert reset，再沿用原有等待与 deassert；实机验收待完成。

随后完整构建主动复位候选 `126a3cd1`，内核、模块与 DTB 校验通过。一轮检查在连接器仍 disabled 时过早尝试读取 DSI 寄存器，随后 USB SSH 丢失；该轮仅 core 捕获有效，没有开始色块，不能作为候选的显示成败结论。改为等待 tegradrmfb 注册、连接器 enabled、两路 runtime active 后才读取寄存器，候选首次初始化自动 A=0/B=768，CPU 四色、GPU 1801 帧／60.018 秒／30.01 FPS、候选 Mesa 下的 Niri＋持续更新终端均由用户确认正常。没有手动改起点或额外 DPMS 恢复循环。Niri modeset 后起点仍正确，180 秒限时结束收到预期 SIGTERM，未见新 SIGSEGV/core；实际三类候选库的进程映射与 SHA256 已核对，干净退出码和 Niri 源码 commit 未确认。第二次有效手动冷启动后，同一内核/DTB 的四色及测试结束恢复的 Linux 控制台也由用户确认正常；第二次没有重复 GPU/Niri/core 测试。详见 [主动复位运行记录](diagnostics/2026-10-10-native-reset-runtime.json) 与 [构建记录](diagnostics/2026-10-10-native-reset-build.json)。自动分段通过本轮有限 RAM 验收；block-linear TEST_ONLY 的 EINVAL 仍用现有线性回退，Noctalia、触控、长期运行、默认原生引导与完整改名后安装仍未验收。

默认引导下的原生桌面与完整改名后安装、音频、蓝牙完整功能、DVFS 和休眠仍未完成。`new_brand_end_to_end_tested` 继续为 false。
