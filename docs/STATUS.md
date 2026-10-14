# 当前状态：2026-10-15 原生桌面与 DFLL 对照

Palmas 步长修复候选通过两次 RAM 冷启动，204/408/612/1020 MHz 请求与独立 PMU 对照通过；实测比请求高约 6%–8%，这些点电压读回均为 900 mV。用户两次确认受限 schedutil 下的完整 Nyxuri、触控、概览图标和顶部弹窗，第一次启动还确认锁屏／唤醒／解锁。20 轮概览及 20 轮控制中心循环后保持 8 个缓冲、40,685,568 字节，32 MiB 及 128 MiB 混合数据 LZ4 回读一致；隔离偏好下真实策略临时运行 40 秒并恢复参数。

默认引导未改变；完整电压曲线、CPU idle 与长期多应用压力尚未验收。原始空 LUT／1.85–1.9 GHz 失败及当前有限证据见 [10 月 15 日对照](DIAGNOSTICS-2026-10-15.md)。

已验收的 `6.12.111-moze.1-native` 和原生 Niri／Mesa／Nyxuri 桌面已持久安装并通过正常开机确认；完整触屏手势、180° 翻转后的画面／坐标、三颗实体触控键及背光、中文浮动键盘和密码锁屏由用户确认可用。本轮概览图标兼容修复与控制中心实际亮度调节也由用户确认正常，键盘去高光并跟随深浅色通过新截图检查。

Tegra/Mesa 导入 scanout GEM 句柄未释放导致图形内存积累。新增引用计数与释放修复通过共享／并发／失败路径回归；实机旧库每 128 个创建销毁操作积累约 8 MiB，新库连续 384 次不增加缓冲数量／容量。新库已持久应用并核对 Niri 与 Noctalia 的实际映射。桌面重启后可用内存约 1.2 GiB，20 轮概览开关后图形缓冲维持 14 个、42,504,192 字节。

0016/0017 补齐 sampler 的两层所有权：借用绑定不消耗 GPU reserve；转交绑定先让 GPU 接管，再释放调用者交出的 wrapper 引用。先前只修 reserve 的候选仍在 20 轮控制中心开关中从 14 个、42,504,192 字节增至 98 个、313,954,304 字节，不能算完整修复。真实离屏 EGL 图像导入／采样对照每批 128 次留下 8 MiB；完整修复累计 384 次只保留当前绑定的 1 个 64 KiB 缓冲，销毁 context 后恢复原计数。最终 Gallium SHA256 `cc81fe6399af38442a48aa52801400086dcb43008aae292353ebac4d65c57fbe` 已持久安装并核对 Niri/Noctalia maps；20 轮概览和 20 轮控制中心开关及随后空闲均保持 7 个缓冲、39,735,296 字节，可用内存约 1.2 GiB。该有限测试不能替代长期多应用检查。

用户再次确认电源熄屏、唤醒和触控密码解锁正常；按键回归扩展为 11 项。

`native-runtime` 内核已完整构建并在独立路径校验；关闭 DFLL、CPU idle 的对照两次进入 Debian，固定 696 MHz，LZ4 zram 的 32 MiB 自有页压缩／读回校验通过，MGLRU/PSI 可读。开启 DFLL 的首次连接失败受早期模块路径干扰，原始重测发现空 LUT 与硬件限频失效；后续 Palmas 步长修复通过上述有限档位和桌面检查。完整动态频率／电压曲线、CPU idle 与长期内存压力未通过，候选没有替换默认引导。长期多应用、深度待机、音频、硬件视频、蓝牙／摄像头／OTG 和原厂前级引导中的关机短按门控／冷充电动画仍未完成。详见 [本轮记录](DIAGNOSTICS-2026-10-14.md)。

# 历史状态：2026-10-12 接续

本轮开始时是默认旧内核/simpledrm，之后通过已验证 RAM loader 临时选择 APP 的 native 内核。全新 Niri/Smithay、Mesa native-sync 和探针构建完成；2 A 墙充下的有限 Niri/Noctalia 同步会话通过，1125 帧全部无需 Niri CPU wait，实际库映射与约 60 FPS 窗口对照已核对。修复测试程序名导致 GPU 策略退回 auto 的问题，11 项会话工具回归通过；正常服务已恢复，默认引导没有更改。PMU 实验模块、长期多应用及其他外设任务仍未完成。见 [本轮记录](DIAGNOSTICS-2026-10-12.md)。

# 历史状态：2026-10-11 远端交接

最新状态与验证条件见 [HANDOFF-2026-10-11.md](HANDOFF-2026-10-11.md)、[未完成任务](TODO.md) 和 [性能 JSON](diagnostics/2026-10-11-native-performance.json)。离开前已运行内置 Debian 的临时原生四核桌面；WC Mesa + 852MHz + 墙充的受控窗口测试约 60FPS，仍有偶发卡顿。新 Smithay fence 检测修复在构建中，完整合成器未验收；原生候选未替换默认引导。设备已带离，本机没有核实之后的画面/供电状态。

扬声器/麦克风、完整 CUDA Runtime、硬件视频编解码、现代内核蓝牙完整功能、摄像头/OTG/休眠仍未完成。全部源码、任务和参数按交接文档继续；以下是保留的历史对照。

# 历史状态：2026-10-10

本轮恢复工作后，通过 Wi-Fi 只读核对：平板已回到原来的 `6.12.111-mocha-experimental-fbdiag` 默认系统，四核在线，电量 85% 且正在充电，显示为 simpledrm；ALSA 仍无声卡。原生候选的先前 RAM 验收不能当作当前默认桌面已切换。新状态快照见 [恢复工作时的状态](diagnostics/2026-10-10-resumed-stable-status.json)。

后续 RAM 实测中，native DSI-1、Tegra DRM、Nouveau 和 Niri 原生渲染节点均已注册；候选 Mesa 缺少 DRI 驱动目录，Noctalia 候选 EGL 初始化失败，系统 Mesa 只能退回 llvmpipe。该会话没有写入 eMMC，也没有改变默认引导；见 [原生桌面会话](diagnostics/2026-10-10-native-desktop-session.json)。

2026-10-09 已恢复 USB SSH 诊断。当时原型机运行旧 release `6.12.111-mocha-experimental-fbdiag`，DRM 是 simpledrm + Nouveau，四核在线，Niri/Noctalia 进程运行，没有失败的 systemd 服务。2026-10-09 该次检查没有重启、写 APP/LNX 或更改默认引导；不能据此宣称改名后的安装通过。只读状态与 fence 原始输出见 [诊断记录](DIAGNOSTICS-2026-10-09.md)。下面既有的性能和面板结论仍来自之前的实机记录。

2026-10-10 RAM 实机验证：U-Boot USB、stable/native 启动与实际 ELF core 捕获通过。native 首轮 CPU/GPU 黑屏，原始驱动重建基线的 DRM 关闭再开启后可恢复图像；与此前成功内核只有 34 字节构建元数据不同，机器指令相同。保留 DSI-B 控制归属与延后分段，补上 Mocha runtime resume 的主动模块复位后，候选首次 CPU 色块、GPU DMA-BUF 色块及候选 Mesa 下的 Niri＋终端均由用户确认正常，没有手动校正或额外 DPMS 恢复。GPU 1801 帧／60.018 秒／30.01 FPS，180 秒 Niri 限时结束未见新 SIGSEGV/core；第二次有效冷启动的四色及恢复后的控制台也正常。两版旧自动候选的失败与一次过早 MMIO 访问干扰的检查仍保留。这只覆盖有限 RAM 验收；默认原生引导、Noctalia 全会话、触控、长期运行与改名后安装仍待完成，APP/LNX 和默认引导未改动。详见 [RAM 诊断](DIAGNOSTICS-2026-10-10.md)。

| 子系统 | 实机状态 | 限制 |
|---|---|---|
| Debian armhf / eMMC | 已持久安装、systemd PID 1 | 仅一台 A0101 验证；GPT 没有重分区 |
| 四核 | CPU 0–3 上线、逐核负载及冷启动通过 | 使用原厂 TLK SMC；CPU DVFS 尚未启用 |
| 默认显示 | 冷启动、横屏、触控、亮度通过 | simpledrm 输出仍有同步/CPU 拷贝开销 |
| 原生 Tegra 双 DSI | 主动复位候选的自动 CPU/GPU/Niri 画面通过有限 RAM 验收，第二次冷启动四色/控制台正常 | 尚未默认启用；Noctalia、触控、长期运行与完整安装待验收 |
| 左右链路 | 保留 DSI-B 控制归属、主动模块复位与延后分段，自动 A=0/B=768 画面正常 | 两次有效冷 RAM 启动及 Niri modeset 通过；不能外推默认安装或长期运行 |
| GPU | Nouveau NVEA / GK20A 硬件着色器通过 | 固件需要自行提取；DVFS/热管理未完成 |
| Wi-Fi | BCM4354 扫描、连接、自动连接通过 | 需要板级 NVRAM 和本机 MAC |
| 触控 | 本机 Atmel maXTouch 1664T 点击、滑动、横屏坐标准确 | Mocha 有不同面板/触控批次，不要盲刷 Synaptics 固件 |
| 充电 | 竖屏动画、按键进桌面、BC1.2 DCP 2 A 输入策略通过 | 最小 Linux 充电模式，并非 SoC 完全断电；电量计偶有跳变 |
| 扬声器/麦克风 | 未完成 | RT5671 0x1c NACK，ALSA 无卡；TFA9890 两颗 revision 可读 |
| 蓝牙 | 旧内核 HCI 初始化通过；现代内核完整功能未验证 | UART/固件/GPIO及配对、音频待完成 |
| 视频播放 | FFmpeg H.264 72 帧解码、Firefox HTML5 播放通过 | 软件解码可用；Tegra124 硬件编解码未完成 |
| 壁纸预览 | 缩略图与专用壁纸目录修复通过 | 需正确安装 Noctalia 数据文件 |
| CUDA | Gdev 实验 Driver API 的有限计算通过 | libcudart 6.5 error 35；完整 CUDA Runtime 未完成 |
| 摄像头 / OTG / 休眠 | 未完成 | 控制器、传感器、VBUS 与恢复链路待适配 |

2026-10-07 暂停时曾运行临时 native6-order；2026-10-09 实测当前已回到 simpledrm 路径。Mesa 空回调修复的主机回归、完整 ARMhf 构建和候选库实机 Nouveau/Tegra 32 轮 fence / 像素回归均通过。原始内核＋手动校正及主动复位候选＋自动校正的 GPU/Niri 画面均通过有限 RAM 验收；完整桌面和默认安装仍待完成。音频仍无 ALSA 卡，蓝牙无 HCI 且 UART 节点被禁用。两套新内核 core 配置通过 olddefconfig，stable/native 完整构建均通过，随后两套内核的 RAM 启动/core 捕获和 U-Boot RAM USB 已通过，主动复位候选两次有效冷 RAM 启动与自动 GPU/Niri 显示已通过有限验收，见上方 2026-10-10 记录。
历史日志存在时间顺序冲突时，以本状态表和后期可复核证据为准。
