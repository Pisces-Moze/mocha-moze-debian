# 2026-10-16 持久启动与充电验证

默认 `native-runtime` 的 uImage／DTB 与匹配模块安装后，经普通启动核对实际 release、文件哈希及活动服务。充电 UI 的实际变换函数覆盖四方向、像素输出覆盖 18 种格式／透明度／缩放组合；用户确认充电方向、自动熄屏后的短暂拔插唤醒与长按进入桌面正常。提前配置输入后的 U-Boot 在 RAM 中确认 released，持久安装并回读校验后，普通插电按住冷启动记录 held／桌面请求 1，用户确认直接进入桌面且充电服务未启动。六项 U-Boot 写功能关闭。详见 [产物、条件及未完成项](DIAGNOSTICS-2026-10-16.md)。尚未完成整盘离线备份、APP 扩容、新 SDIO 属性下的 suspend/resume 或长期负载验收。

# 历史验证：2026-10-15 实机与回归验证

默认原生内核、全量 Nyxuri 桌面、旋转触控、实体导航键、密码解锁、概览底部图标和控制中心亮度已有用户确认。深浅色键盘截图通过；ARM Luau 1,000 次真实库状态创建／释放回归通过。导航 5 项、电源／音量按键 11 项、充电 generator 2 项、临时启动流程 4 项与运行时策略 9 项、DFLL 步长实际函数 10 项回归通过。

Mesa 可选 fence 8 种组合、reset/scissor 4 种组合、modifier 6 次往返和 4,084 种非目标布局检查通过。新增 scanout 生命周期回归覆盖共享句柄、独立句柄、零句柄、失败分配／导入及 8 线程并发导入／释放。真实 Tegra GBM 创建销毁 384 次对照显示：旧库逐批积累 8 MiB，新库缓冲容量不增长；新库在 Niri/Noctalia 中实际加载，20 轮概览开关后缓冲计数不增长。

0016/0017 补齐 sampler 的两层所有权：借用绑定不消耗 GPU reserve；转交绑定先让 GPU 接管，再释放调用者交出的 wrapper 引用。先前只修 reserve 的候选仍在 20 轮控制中心开关中从 14 个、42,504,192 字节增至 98 个、313,954,304 字节，不能算完整修复。真实离屏 EGL 图像导入／采样对照每批 128 次留下 8 MiB；完整修复累计 384 次只保留当前绑定的 1 个 64 KiB 缓冲，销毁 context 后恢复原计数。最终 Gallium SHA256 `cc81fe6399af38442a48aa52801400086dcb43008aae292353ebac4d65c57fbe` 已持久安装并核对 Niri/Noctalia maps；20 轮概览和 20 轮控制中心开关及随后空闲均保持 7 个缓冲、39,735,296 字节，可用内存约 1.2 GiB。该有限测试不能替代长期多应用检查。

`native-runtime` 搭配 DFLL 关闭的已验收设备树、`cpuidle.off=1` 两次进入 Debian，USB/Wi-Fi SSH 可用，CPU 固定 696 MHz。LZ4 zram 的 32 MiB 自有匿名页 pageout／SHA256 读回通过，MGLRU/PSI 可读。原始 DFLL 开启重测的 204 MHz 请求对应约 1.85–1.9 GHz，限频验收失败。Palmas 电压表步长修复后，两次 RAM 冷启动；204/408/612/1020 MHz 请求与独立 PMU 对照通过，实测比请求高约 6%–8%，这些点电压读回均为 900 mV。受限 schedutil、完整 Nyxuri、触控、概览图标、顶部弹窗和锁屏／唤醒／解锁由用户确认；20 轮概览及 20 轮控制中心循环后保持 8 个缓冲、40,685,568 字节，32 MiB 及 128 MiB 混合数据 LZ4 回读一致；隔离偏好下真实策略临时运行 40 秒并恢复参数。默认引导未改变；完整电压曲线、CPU idle 与长期多应用压力尚未验收。 策略启动前及改变上限后保持原误差阈值，要求同一请求连续两次反馈匹配，拒绝持续错误与偶然单次匹配。见 [DFLL 实测](DIAGNOSTICS-2026-10-15.md)。详见 [本轮诊断](DIAGNOSTICS-2026-10-14.md)。

# 历史接续验证

2026-10-12：帧统计回归 5 项、Linux 隔离服务流程回归 11 项、模拟 Fastboot 引导流程 3 项通过。新 Niri/Smithay、Mesa native-sync 和三个 ARMhf 探针完整构建并核对哈希；旧内核前置检查拒绝运行且原桌面 PID 未变。2 A 墙充下有限原生 Niri/Noctalia 会话通过：1125 帧均无 Niri CPU wait、capability/真实加载库/600 帧窗口/服务恢复取证完成，另做关闭逐帧插桩对照及 80 轮独立 EGL native-fence 检查。新 KMS 探针本轮因无活动控制台 CRTC 拒绝运行，未报告新的 scanout pass。默认引导没有更改，长期多应用和 PMU 候选仍待验证，见 [本轮记录](DIAGNOSTICS-2026-10-12.md)。

# 历史整理与发布的验证范围

2026-10-08发布验证针对源码和安装资料；按用户要求暂停实机开发，本次没有重启、刷写或更改平板。

| 检查 | 结果 | 实际范围 |
|---|---|---|
| Linux完整源树 | 86,744个Git跟踪文件 | Debian原始基线、Mocha变更与规范化构建提交分离 |
| 两种设备树 | stable-desktop/native-experimental均由dtc生成DTB | 警告保留；编译成功不代表外设运行完成 |
| stable内核配置 | olddefconfig通过，kernelrelease=6.12.111-moze.1 | 没有重新构建并刷机验收整个新命名内核 |
| 充电UI | ARM交叉编译通过 | 原机此前竖屏充电/按键已实测；新统一安装路径未重刷 |
| DMA-BUF色块、CUDA probe | ARM交叉编译通过 | 之前实机色块可见/有限CUDA计算通过，不代表完整桌面或runtime |
| Android U-Boot封装器 | 已用实际U-Boot ELF/payload检查头部、长度、载入字段和SHA1 | 新容器名称导致哈希变化，没有新刷机验收 |
| 脚本、配置 | 逐个shell语法、Python AST、TOML/JSON解析 | 构建依赖配置核对实际Linux VM资料；规范化安装未端到端跑完 |
| 多仓库来源 | 上游tag/revision、Linux源压缩包SHA256、四仓库commit锁 | 上游下载仍需网络，构建产物需开发者自己计算哈希 |
| 公开内容筛选 | 项目文件排除凭据、设备备份、校准、专有固件和编译镜像 | 上游Linux测试样例仍保持原始源码，不能按字符串判定为私人凭据 |
| GitHub上传 | 五个public仓库，远端main与本地提交逐一对照 | repos.lock.json锁定其余四仓库的配套版本 |

不能把本表的静态/交叉编译验证称为“新版本已可一键刷入”。参考[安装指南](INSTALL.md)逐级RAM、APP、LNX验证；待解决的问题在[ISSUES.md](ISSUES.md)。

## 2026-10-09 继续诊断

- USB SSH 实际读取旧内核、四核、DRM、ALSA、蓝牙、电源和存储状态；未重启或写 APP/LNX。采集脚本只读取白名单字段，不收集设备身份、命令行、环境变量和任意 journal 内容。
- 原有 Mesa / Nouveau / NVEA 的 32 轮 EGL fence 跨上下文等待和红/绿像素检查通过；未覆盖 Tegra 包装层，也未观察面板。
- Mesa 官方 25.0.7 归档 SHA256 校验、补丁 hunk 检查与主机 C 回归完成：原始源码失败，候选源码的八种回调组合通过，转发参数检查通过。Debian 13 上完整 ARMhf 交叉构建已通过。
- 同一原型机用独立 EGL probe 强制 Tegra 包装层，在 `eglWaitSyncKHR` 重现 SIGSEGV。GDB remote 的 PC/R3 为零，实际 Thumb BLX R3 指令、LR 的 `+0xd645bc` 与运行库 Build ID 均与历史 Niri 调用点吻合；未切换 native 内核或改变现有桌面。
- 候选 Mesa 在同一原型机的独立数据目录运行，Nouveau 与 Tegra 包装层均通过 32 轮 EGL fence 和像素检查。实际加载的三类 Mesa 库均来自候选目录，Tegra 不再 SIGSEGV；原有桌面仍运行。native KMS、Niri、面板与 zero-copy 验收仍待完成。
- `/proc/config.gz` 确认运行内核关闭 `CONFIG_ELF_CORE`。公开 stable/native 配置已启用并增加构建断言；两份配置的 `olddefconfig` 均保留三个 core 前提选项，stable 的 Image/uImage、模块和 DTB 完整构建通过。native 完整构建随后也通过；临时启动和实际 core 捕获仍待完成。
- 新 Python 工具语法、Meson cross file 解析通过；板上 `--require-tegra` 正确拒绝 Nouveau 节点。

具体状态、验证边界和下一步见 [诊断记录](DIAGNOSTICS-2026-10-09.md) 与 desktop 仓库的 [MESA-FENCE.md](https://github.com/Pisces-Moze/mocha-moze-desktop/blob/main/docs/MESA-FENCE.md)。

## 2026-10-10 RAM 验收

2026-10-10 RAM 实机验证：U-Boot USB、stable/native 启动与实际 ELF core 捕获通过。native 首轮 CPU/GPU 黑屏，原始驱动重建基线的 DRM 关闭再开启后可恢复图像；与此前成功内核只有 34 字节构建元数据不同，机器指令相同。保留 DSI-B 控制归属与延后分段，补上 Mocha runtime resume 的主动模块复位后，候选首次 CPU 色块、GPU DMA-BUF 色块及候选 Mesa 下的 Niri＋终端均由用户确认正常，没有手动校正或额外 DPMS 恢复。GPU 1801 帧／60.018 秒／30.01 FPS，180 秒 Niri 限时结束未见新 SIGSEGV/core；第二次有效冷启动的四色及恢复后的控制台也正常。两版旧自动候选的失败与一次过早 MMIO 访问干扰的检查仍保留。这只覆盖有限 RAM 验收；默认原生引导、Noctalia 全会话、触控、长期运行与改名后安装仍待完成，APP/LNX 和默认引导未改动。详见 [RAM 诊断](DIAGNOSTICS-2026-10-10.md)。

捕获 core 时未挂载 eMMC，之后 Mesa/GPU 测试只以 ro,noload 挂载 APP/数据；原始 core、固件与编译镜像未发布。KMS 翻页成功与约 30 FPS 不代表面板输出成功。
