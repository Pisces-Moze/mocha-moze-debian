# 当前状态：2026-10-10

2026-10-09 已恢复 USB SSH 诊断。当时原型机运行旧 release `6.12.111-mocha-experimental-fbdiag`，DRM 是 simpledrm + Nouveau，四核在线，Niri/Noctalia 进程运行，没有失败的 systemd 服务。2026-10-09 该次检查没有重启、写 APP/LNX 或更改默认引导；不能据此宣称改名后的安装通过。只读状态与 fence 原始输出见 [诊断记录](DIAGNOSTICS-2026-10-09.md)。下面既有的性能和面板结论仍来自之前的实机记录。

2026-10-10 RAM 实机验证：新 U-Boot USB、stable/native 内核启动与实际 ELF core 捕获通过；stable 日志画面正常。真实 Tegra 节点的候选 Mesa fence 回归通过；native 首轮 CPU/GPU 色块黑屏；原始内核恢复 native5 控制归属并手动校正后，CPU/GPU 色块与候选 Mesa 下的 Niri＋终端已由用户确认正常。两版新驱动自动校正均黑屏，同一个新内核关闭自动校正也黑屏，原因仍待排查。自动分段、Noctalia 全会话、触控与改名后完整安装仍未通过，默认引导及 APP/LNX 未改动。详见 [RAM 诊断](DIAGNOSTICS-2026-10-10.md)。

| 子系统 | 实机状态 | 限制 |
|---|---|---|
| Debian armhf / eMMC | 已持久安装、systemd PID 1 | 仅一台 A0101 验证；GPT 没有重分区 |
| 四核 | CPU 0–3 上线、逐核负载及冷启动通过 | 使用原厂 TLK SMC；CPU DVFS 尚未启用 |
| 默认显示 | 冷启动、横屏、触控、亮度通过 | simpledrm 输出仍有同步/CPU 拷贝开销 |
| 原生 Tegra 双 DSI | 历史 native5 GPU 色块可见；本轮恢复控制归属后 CPU 色块可见 | 原始内核＋手动校正的 GPU/Niri 已确认正常；新镜像自动方案失败，尚未替换默认路径 |
| 左右链路 | native5 控制归属下，手动设置 A=0/B=768 后用户确认色块位置正常 | 自动校正版本虽有正确起点读数，仍物理黑屏；不能据寄存器值判定通过 |
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

2026-10-07 暂停时曾运行临时 native6-order；2026-10-09 实测当前已回到 simpledrm 路径。Mesa 空回调修复的主机回归、完整 ARMhf 构建和候选库实机 Nouveau/Tegra 32 轮 fence / 像素回归均通过。原始内核＋手动校正的原生 GPU/Niri 画面已通过本轮有限 RAM 验收，自动方案和完整桌面仍待完成。音频仍无 ALSA 卡，蓝牙无 HCI 且 UART 节点被禁用。两套新内核 core 配置通过 olddefconfig，stable/native 完整构建均通过，随后两套内核的 RAM 启动/core 捕获和 U-Boot RAM USB 已通过，当前 native 面板黑屏，见上方 2026-10-10 记录。
历史日志存在时间顺序冲突时，以本状态表和后期可复核证据为准。
