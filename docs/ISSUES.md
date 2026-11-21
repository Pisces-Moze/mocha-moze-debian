## 2026-10-25 最小 CUDA 语言模型已部署

TinyStories 260K（约 1 MB）已部署，普通用户可运行 `mocha-cuda-llm -n 96`。五层 Transformer 前向合并为每个 token 一个 sm_32 CUDA 内核；96 步、49,152 个 logits 的 CPU 对照错误为 0，生成文本完全一致。普通命令关闭 CPU 对照后另行通过，CUDA 约 12.7 token/s，进程 RSS 5308 KiB；这个极小模型的 CPU 版本仍更快，不作为加速性能结论。用途为英文生成及 CUDA 链路验证，完整 Runtime 兼容仍按既有待办推进。源码与结果见 drivers 仓库 `cuda/LLM.md`、`cuda/validation-llm-2026-10-25.json`。

## 2026-10-25 开放 CUDA Runtime 已安装，计算与内存路径通过

Gdev/Ocelot Runtime 已在当前原生内核上持久安装，普通 mocha 用户自检通过。NVCC 6.5 生成的 sm_32 程序在 257／8193 元素下完成浮点 SAXPY、静态／动态共享内存归约、原子加法、混合整数／结构体参数、锁页内存、二维拷贝、流与事件检查，逐项输出正确；旧 Driver API 整数样例仍通过。内部指针 ABI、ELF32、fatbinary 边界、参数偏移和内核属性已修复，私有依赖补齐。

当前 Runtime 报告 3020，Driver 4000。执行仍串行，事件为主机完成时间；PTX 即时编译、真正并发、纹理／全局符号、托管内存和官方库完整兼容继续列为待办。官方 libcudart 6.5 的 error 35 未宣称解决。源码、构建入口、安装命令和实机记录见 drivers 仓库 `cuda/README.md`、`cuda/validation-2026-10-25.json`。以下保留此前阶段记录。

## 2026-10-25 启动动画已持久安装并通过普通开机验收

最终 #9 内核、initramfs 和 LNX 已正式安装并回读核对；普通冷启动后再次确认默认文件、整段 LNX、实际运行内核与 Niri 桌面一致，用户确认动画、滚动日志及桌面正常。原生动画在约 1.85 秒挂接，直接 DMA 更新警告已修复。头像和底部标识静止，定时器仅更新 64×64 加载圈，原生日志滚动区域按需重绘。实机与电脑均保留配对回退备份，本轮未改动桌面效果或壁纸设置。

## 2026-10-25 RAM 桌面已验证，提前显示与加载圈优化待复测

已核对候选内核 #5、动画启动参数、原生动画符号和 Niri，用户确认正常进入桌面，同时报告开机加载圈卡顿和 Linux 期间黑屏。日志显示面板在 28.76 秒才接上；背光模块排在桌面硬件服务末尾。新独立 initramfs 提前加载同一已验证模块，保留根分区检查和正常用户空间重试；加载圈改为直接解码透明度、按像素格式预先计算颜色，原生日志字形保留。新完整内核和两种 U-Boot 已构建、下载校验，49,152 次实际渲染像素比对及 ASan/UBSan 通过；已从 RAM 启动，默认启动文件尚未替换。

## 2026-10-25 启动环境根因已定位并修正，RAM 复测待完成

动画测试 `.env` 的首行 `#` 说明被生成为 `=# RAM test profile...`，U-Boot 环境导入器因空变量名返回 EINVAL；导入失败后才出现 32 字节缓冲区截断。删除该说明行，保留失败检查，构建工具新增对 ELF 符号及实际 payload 内完整环境表的校验。旧错误镜像被检查工具拒绝，新测试／正式镜像均通过并已下载。修正版 RAM 启动后，用户确认已显示 Linux 充电动画，当前需先充电；尚未确认桌面交接，默认引导未写入。

## 2026-10-25 RAM 观察：动画已显示，环境初始化修正版待启动

实机已显示原头像、两行 Debian 标识、加载圈和默认 U-Boot 日志，但提示 `env_buf [32 bytes] too small`，长启动命令被截成 `boot_`，未进入 Linux。修正版在板级 late init 确保编译内置环境已导入 RAM，并检查电源键环境变量写入结果；测试和正式 U-Boot 已完整重建、下载校验，内核未改。默认引导尚未写入，需先确认修正版完成 Linux／桌面交接。记录见桌面仓库 `validation/boot-log-animation-2026-10-25.json`。

## 2026-10-25 两行 Debian 标识与加载圈优化，启动包已完成

底部恢复 powered by／debian＋旋涡图标的两行布局，Moze 仍在最底部。加载圈为 120 帧／2.4 秒、3.5 像素圆头弧线、4×4 抗锯齿，首尾持续顺时针前进。ARM32 毫秒换算改用 div_u64，完整内核与测试／正式引导均已构建、下载校验并暂存，原默认内核未替换。新备份已在平板和电脑双份核对。用户已授权持久安装，正在等待手动进入 Fastboot 后完成一次 RAM 显示及桌面交接确认，再写入与回读。见桌面仓库 validation/boot-log-animation-2026-10-25.json。

## 2026-10-23 底部单行 Debian 与 Moze，准备持久安装

按最新要求，powered by debian 与官方旋涡图标改为屏幕底部一行，Moze 单独置于最底部，保持竖屏原头像、纯黑、加载圈与默认日志。官方 Google Sans 字体和 Debian 图标来源及许可已随源码保留。新完整内核与配对的测试／正式 U-Boot 正在构建。新备份已在平板和电脑双份验证；用户已授权刷入，完成 RAM 验收后执行写入与回读，目前默认引导尚未更改。

## 2026-10-23 竖屏启动动画更新

采用原头像透明底，1536×2048 纯黑竖屏，上方居中头像、下方白色伸缩加载圈；移除字标和额外文字。默认 U-Boot／Linux 控制台日志继续直接叠加。选定资产的 U-Boot ARM 完整构建及 earlycon／fbcon 对象编译通过，实机 RAM 启动与交接尚待验收，未改默认引导。

# 2026-10-23 原生 Firefox 硬解与启动动画候选

Firefox 新增原生 stateless V4L2 Request 候选补丁，三平面 DRM 描述符的 27 项 ASan/UBSan 检查及 ARMhf 交叉配置通过，153.5.1esr 完整构建正在进行。RDD 沙箱和站点隔离保留，开关默认关闭。当前实机浏览器尚未替换，VDE 的 CABAC 等格式限制仍在；不能把已有 MPV 硬解当成 Firefox 硬解验收。

按用户最新选择，使用原头像去除深色背景的透明 PNG，纯黑画布；不采用重绘图标。标准 U-Boot vidconsole、原始 Linux earlycon 及原生 fbcon 只增加背景合成，日志字体和滚动由原控制台负责。选定资产的 U-Boot ARM 完整构建及 earlycon.o／fbcon.o 编译通过。上一版用户空间日志服务已停用、移入备份，Niri 入口已恢复。默认引导未替换；完整候选内核和 RAM 实机的旋转、日志可读性、DRM 交接仍待验证。预览回放实机原始日志，不代表新引导已通过验收。

证据见桌面仓库 `validation/firefox-request-candidate-2026-10-23.json` 和 `validation/boot-log-animation-2026-10-23.json`。以下保留历史状态。

# 2026-10-23 浏览器视频高负载：已避开 AV1，硬解仍待接入

B 站最低画质实际使用 AV1 软解，两个 dav1d 线程在 4 秒样本中合计约占单核 61%。AVC 优先和低内存默认值已持久安装并重启生效；用户恢复同一视频后为 H.264，RDD 约占单核 25%，但主进程和网页仍约 92%／72.3%。当前 Firefox 未接入 V4L2 Request，不能将格式回退称作硬解完成。

播放中 MemAvailable 约 446 MiB、memory PSI avg10 为 0；短快照不足以断言长期内存问题解决。继续定位网页／渲染 CPU、补齐 VDE CABAC 与浏览器集成；不强开 VA-API、不关闭沙箱、不清系统缓存。详见桌面仓库 `docs/BROWSER-PERFORMANCE.md` 与 `validation/browser-low-memory-2026-10-23.json`。以下为历史记录。

# 2026-10-22 内置双扬声器已打通并持久安装

用户确认左右两侧均有声音。PX5 拉高解决 RT5671 应答，修正 DAP1 DOUT 三态、DAC1 总播放开关和 AIF2 数字转发；双 TFA 使用工厂校准与完整保护固件，通过下载读回后才放音，没有写入 MTP。桌面默认输出为“Mocha 内置扬声器”，PipeWire 普通应用播放通过，48 kHz／S16／立体声；空闲后 PCM 关闭、两颗功放断电。

六个匹配 VDE2 的模块、带哈希核对的加载器、systemd 开机服务及 WirePlumber 输出配置已持久安装。服务停止／启动通过，未重复重启验收；开机自动加载已配置，但安装后的冷启动尚未复测。耳机、麦克风和其他采样格式不在本轮完成范围。实现与验证见驱动仓库 `audio/README.md`、`audio/validation-2026-10-22.json`。以下为此前阶段记录。

# 2026-10-22 命令缓冲上传降耗，接续内置扬声器

Mesa 新增 GK20A 命令缓冲的 WC 分配策略，覆盖初始 ring 与后续增长，保留内核同步和导入缓冲的所有权规则。8 项策略回归及五套既有源码检查通过，已带备份持久安装，并核对 Niri、Noctalia、mpvpaper 的实际加载库。约 8 秒短采样中 Niri CPU 从单核的 49.16% 降到 37.70%，其中内核时间从 33.31% 降到 18.42%；这是有限窗口，不能代表长期帧时间。硬解、画质、毛玻璃和效果设置保持原样。用户确认“卡顿减轻”，仍保留残余卡顿代办；诊断 preload 已移除，空闲锁屏策略已恢复。证据见桌面仓库 `validation/mesa-command-upload-2026-10-22.json`。

用户当前明确优先处理内置扬声器。先定位 RT5671 通信失败，再接通真实声卡和受保护的双功放路径；工厂校准保持不变。以下为此前阶段记录。

# 2026-10-21 输入与工作区壁纸释放已通过实机检查

菜单搜索与 Wi-Fi 密码框均已由用户确认可用。除键盘层级和点击拦截区域修复外，新增 `0022-niri-touch-keyboard-focus.patch`：只在点击不接受键盘焦点的主键盘／候选层时保留 OnDemand 面板的文本焦点，其余点击规则保持原样。三项原生焦点回归通过，保留原有样式、候选窗和输入隐私。证据见桌面仓库 `validation/keyboard-popup-focus-2026-10-21.json`。

用户需要的“全屏”包括任务栏仍可见的占满工作区。新增 schema 2 工作区联合覆盖信号及插件消费逻辑；首次实机已确认占满工作区时播放器／holder 0、VDE suspended／引用 0，概览时恢复。两个半宽窗口的分数缩放细边导致首次候选未释放，追加 2 逻辑像素取整容差和第四项几何回归。最终 ARMhf 候选与插件已带备份持久安装；恢复 USB 后的集中实机检查全部通过：占满工作区及两个半宽窗口均为播放器／holder 0、VDE suspended／引用 0，概览和控制中心保持播放，露出桌面恢复 Request 硬解。前次黑屏及 USB 中断缺少上一轮日志和 pstore，原因仍未确定。弹窗与概览期间继续播放，毛玻璃、透明度和画质保持原设置；不据此声称交互卡顿已解决。详见 `validation/wallpaper-workarea-2026-10-21.json`。以下为此前阶段记录。

# 2026-10-21 虚拟键盘与弹窗输入

实机核对发现控制中心也在 Overlay，单纯提升键盘层级不够。追加 `0021-noctalia-touch-keyboard-input-region.patch`：主键盘与独立候选窗发布可点击几何，弹窗透明拦截层排除这些区域；文件事件更新，正常隐藏后恢复拦截，进程异常退出时清除旧区域。保持 KeyboardMode.NONE、不接受焦点、原有样式和触摸反馈，不记录输入内容。旋转／分数缩放／其他输出／异常数据的原生几何回归通过 ASan/UBSan，ARMhf 构建和三端哈希通过。键盘与桌面壳均已带备份安装，首次健康检查显示任务栏可见、会话未锁定。

随后 Wi-Fi SSH 超时；USB 接入后确认同一桌面壳、键盘服务与搜索菜单仍正常运行，Wi-Fi 接口仍显示连接，未见新的 GPU 故障日志。Wi-Fi 管理连通性的原因仍待定位；两种弹窗的真实触屏输入仍待确认。不能把安装健康检查当作完整验收。证据见桌面仓库 `validation/keyboard-popup-focus-2026-10-21.json`。

# 2026-10-20 实际遮挡释放已安装

Niri 现在按背景／X-Ray render-element 的实际可见性提供会话状态，插件复用 1 Hz 更新，持续遮挡默认 2 秒后释放播放器。实机关闭旧前台全屏策略进行隔离检查：全屏及两个不透明窗口联合覆盖均为播放器／holder 0、VDE suspended／引用 0；概览、控制中心和露出桌面均恢复 Request 硬解。原静态选择与诊断配置已恢复。多输出与异常会话由源码回归覆盖，透明窗口仍可见的背景不被误停。持久安装的源码检查通过；七种补丁前缀的安装器回归通过。

这解决遮挡资源释放，动态壁纸交互的 CPU 开销和卡顿仍未解决。更全面视频硬解、浏览器集成、RT5671 声卡／扬声器和完整 CUDA Runtime 继续保留代办。参见桌面仓库 `validation/wallpaper-occlusion-2026-10-20.json`；下方为此前阶段记录。

# 2026-10-19 蓝牙上电与 HID 输入

BCM4354 上电时先释放 RTS、退出 shutdown 后再恢复流控，修复了此前仅 Reset 应答的问题；固件加载、扫描和 S102 持久配对已通过，PipeWire 蓝牙输出由用户确认有声音。匹配 VDE2 的显式蓝牙模块、启动服务、UHID／uinput 已持久安装。ThinkBook 鼠标和 K480 均已保存绑定、信任、连接并建立内核输入节点；常规打字／鼠标动作尚未单独确认。Noctalia 蓝牙代理的重注册与键盘信息提示生命周期修复已编译、带备份安装并重载；K480 已由用户完成配对码输入及此前所需的手动连接；随后追加配对成功自动信任／连接与数字清理修复，真实回调回归通过并持久安装，保留现有绑定。

内置扬声器仍未通过：RT5671 在保持厂商供电／时钟后仍 NACK，软件复位也未应答，ALSA 无内置声卡；诊断时钟恢复顺序已修正并核对恢复值，没有音频探针残留。详见驱动仓库的蓝牙本轮记录与 audio/README.md。另核对 Niri 的 NVIDIA 显存说明：实机 nouveau／Mesa 不使用专有驱动 profile，六轮弹窗后的 DMA-BUF 总量回到原值，未排除长期问题。下方是历史状态，不能将旧的“蓝牙未应答”视为本轮结论。

# 已遇到的问题与实现思路

## 2026-10-18 外设初始化排查

蓝牙在默认 VDE2 下能收到 HCI Reset 成功应答，随后版本读取超时。保持 UART 运行时供电、隔离 PIO／原始 TTY、唤醒线对照、复位后立即请求下载及主机端换速均未恢复后续应答；默认 UART 驱动已恢复，临时模块已卸载，没有上传固件。详见 [驱动诊断](https://github.com/Pisces-Moze/mocha-moze-drivers/blob/main/bluetooth/README.md)。音频在匹配模块下临时使能 32 kHz 和 12.288 MHz 时钟后，RT5671 的 0x1c 仍 NACK，两颗 TFA revision 为 0x0080；没有写 MTP，ALSA 仍无声卡，不能称蓝牙／扬声器可用。

## 2026-10-16 持久安装与充电启动

运行系统已提升为持久 `native-runtime` 并确认普通启动。充电动画方向、短暂拔插线重新亮屏，以及插电按住电源直接进桌面均通过本机用户观察；最后一项同时记录到 U-Boot 提前采样为 held、Linux 桌面请求为 1、充电服务未启动。APP 已离线扩至 3 GiB，整盘离线备份已验证，原有备用 GPT 数组重叠已修复，旧 L4T 已按授权清理；桥接普通启动已通过，离线迁移已通过，扩容后普通启动、实际空间和用户桌面验收也已通过；其他外设任务依用户顺序后置。原厂前级短按门控、完整频率／电压曲线和长期压力测试不能据此标为解决。见 [本次证据](DIAGNOSTICS-2026-10-16.md)。

## 2026-10-15 DFLL 硬件控制

DFLL 开启重测已进入 Debian，软件请求 204 MHz、上限 612 MHz，但 monitor 与独立 PMU 估算均约 1.85–1.9 GHz。停止桌面／GPU 负载与升频测试，保留原默认内核；运行时策略新增硬件反馈检查，六项回归通过。闭环、输出 scaler 和 PMIC I2C/LUT 仍需定位，不进行猜测性电压修改。见 [实测记录](DIAGNOSTICS-2026-10-15.md)。

## 2026-10-14 桌面细节与图形内存

概览 Dock 图标的 mipmap 采样产生碎条，原始 SVG 正常。只对 Dock 图标启用线性采样后新截图及用户观察正常，其他 Nyxuri 图片、毛玻璃与动画保持原路径。亮度显式映射实际背光节点，用户确认滑块可改变屏幕亮度；GTK 键盘去高光并跟随主题。空桌面返回／主页避免重复 IPC 操作和输入注入。

Tegra wrapper 导入 scanout GEM 句柄后没有对应释放，图形缓冲在应用退出后积累。引用计数处理重复 PRIME 句柄，最后释放时关闭一次；实机 384 次创建销毁对照验证新库不再按批增长，桌面已使用修复库。长期多应用仍需测试。sampler 借用／转交引用释放也已修复，20 轮概览与控制中心开关后图形缓冲维持约 38 MiB。CPUFreq/DFLL 与 zram 的新内核候选已构建，不能据此称为调频／降压／长期内存稳定性通过。

下方保留历史问题与当时的诊断状态；最新验收边界以 [STATUS.md](STATUS.md) 和 [本轮记录](DIAGNOSTICS-2026-10-14.md) 为准。

## 完整会话性能验收的环境与恢复问题（2026-10-12）

原 prototype profile 的 `native-sync` 只为合成器选择新 Mesa，窗口基准仍使用 WC 库，导致两组数据条件不一致；固定 runtime override 在前置检查失败时也会被删除并重启桌面。现在共用库环境，先验证 native 内核/DSI/候选文件，再用锁和独占配置临时切换，按 MainPID 和对应 socket 取证；失败及可捕获的终止信号后恢复服务。帧日志缺失字段不再当作无需同步，KMS 探针的部分帧/零 pending exports 不再报告 pass。另修复基准提前关闭返回成功、缺完整帧记录与 profiler 名称导致 `pidof niri` 失配退回 auto。11 项隔离回归及有限原生桌面同步验证通过；见 [接续记录](DIAGNOSTICS-2026-10-12.md)。

## 一核 → 四核
默认主线安全复位注册接口与原厂 TLK 不匹配，CPU reset vector 被安全世界锁定。参考官方 reset/platsmp/tegra_sm_interface 后，对 `nvidia,mocha` 且显式 opt-in 的设备调用 SMC `0x82000001` 设置分发器，再使用 Tegra PMC/flow-controller 的 SMP 操作。四核冷启动和负载通过；这不意味着 CPU DVFS、热管理或 suspend 完成。

## 冷启动半屏变色，Fastboot 正常
同一镜像在 Linux 前已出现左右颜色不同，排除仅由 compositor 引起。读回 DC/双 DSI 的继承状态，参考官方复位顺序，在 U-Boot 面板复位前停止继承视频/ganged/电源状态，再成对发送初始化命令。早期只有 Linux reset 延时修正不足；最终 U-Boot 交接修复的两轮冷启动通过。

## PMIC 初始化后屏幕逐渐熄灭
通过早期色条、early framebuffer、initcall 暂停把阶段缩小到 I2C/PMIC。禁用探测能维持显示，但这只用于定位。
恢复 GPIO后显示稳定，恢复外部控制供电又熄屏。去除 CPU/core/PLL 外部控制声明后正常 Palmas 供电注册通过。尚不能把故障归因于某一路寄存器单独写入，也不声称所有继承电压完全不变。

## USB gadget 未连接
device 角色和 PHY dr_mode 必须一致。配置 gadget 成功但 UDC `not attached`、VBUS=0，最初 RAM B-session 覆盖可定位，之后恢复真实 PMIC 会话检测。
重新进入 target 时重复写已绑定 gadget 导致 SSH服务失败：复用 gadget，恢复地址/接口，并把 Wi-Fi SSH对USB服务的 Requires 改为 Wants。
部分大文件/U-Boot尾块传输仍发生卡住；限速和固定块减少失败，根因未彻底确认。
软件 `reboot-argument=bootloader` 实测进入 APX（0955:7015），不能宣称它能返回原厂 Fastboot。

## 桌面左侧四分之一黑条
物理 framebuffer 1536×2048，Niri 横屏后 damage 坐标仍未完整转换，最后512行未提交。临时 legacy KMS 绕开 damage 属性消除黑条；Smithay 补齐旋转 damage 后实际画面通过。需要区分“正确显示”与“没有CPU拷贝”。

## 原生双 DSI 黑屏与左右反转
Linux ganged video 路径原先按整行给每链路，并用非 ganged SOL。按官方公式分拆，1536×2048 下每链路 active=2304 字节，HBP70/HFP196/SOL334。
Tegra DCS short write返回4字节线头，不是payload长度；修正误判。MIPI calibration mask按Tegra124 DSIA/B与CILC/D选择0x60/0x0c。
初始化前停掉继承的视频并使用LP命令。原先 LP68MHz下 pageflip/CRC变化仍黑屏；改为已验证U-Boot命令阶段的12MHz后用户看到4个GPU色块，约29.8FPS，不含CPU像素copy/readback。
54300000链路必须start0，54400000必须start768。live改寄存器被modeset覆盖；native6设备树把543作为primary、544作为secondary，桌面modeset后读数仍正确。但用户仍报告日志从屏幕中间开始、右侧内容绕回左边和位置错误；寄存器正确不代表最终画面坐标、stride、格式和控制台均已验证，暂停前尚未完成修复。

## Niri native SIGSEGV：fence 回归通过，桌面待验收
block-linear framebuffer的atomic TEST_ONLY返回EINVAL，随后fallback启动，但Mesa/Gallium内部跳到PC=0；实际GDB捕获LR并匹配库Build ID。不是凭“黑屏”猜测。
先前 Mesa 25.0.7-2+deb13u1 Build ID fd7dcad10de8c89211ebe69ae8c8dda302f047d0，返回偏移0xd645bc，匹配 Debian 调试符号为 `tegra_fence_server_sync`，`src/gallium/drivers/tegra/tegra_context.c:834`。当时只定位到调用点；下文记录本轮的源码确认与候选实机回归。
CONFIG_COREDUMP=y但CONFIG_ELF_CORE关闭，第一次core捕获没有生成文件；改用ARM gdbserver抓栈。
后续仍需验证真实 native 桌面及缓冲区协作，再测 DMA-BUF、CPU_PREP 和 copy；当前不能标注 Niri zero-copy 完成。

2026-10-09 已对照 Mesa `mesa-25.0.7` 的固定源码，确认 Tegra 无条件注册 `fence_server_sync` 包装回调，但 Nouveau 没有实现底层回调；`create_fence_fd` / `fence_get_fd` 也存在同类转发问题。desktop 仓库的 `0004` 补丁仅在底层回调存在时注册包装层，原始源码回归失败、修复后八种回调组合通过。原型机原有 Nouveau 路径另通过 32 轮 EGL fence 测试，作为系统库对照。

同日读取原型机 `/proc/config.gz`，确认 `CONFIG_ELF_CORE` 实际关闭。linux 仓库已启用 stable/native 两套配置中的该选项，并增加构建检查；两套配置均通过 `olddefconfig`，stable/native 完整构建均已通过，两个 vmlinux 都含 elf_core_dump。2026-10-10 两套新内核已在 RAM 实际捕获 ELF core，见 [RAM 诊断](DIAGNOSTICS-2026-10-10.md)。

随后在当前 simpledrm 系统上，仅为无 modeset 的独立 EGL probe 设置 `MESA_LOADER_DRIVER_OVERRIDE=tegra`，实机在 `eglWaitSyncKHR` 重现 SIGSEGV。GDB remote 捕获 `PC=0`、`R3=0`，调用指令为 Thumb `BLX R3`，LR 规范化后为 libgallium `+0xd645bc`；运行库 Build ID 与历史 Niri 的 `fd7dcad10de8c89211ebe69ae8c8dda302f047d0` 相同，空回调来源得到运行时确认。

完整交叉构建后，候选库在同一设备上通过 Nouveau 与进程级 Tegra 的 32 轮 fence / 共享像素回归，`eglWaitSyncKHR` 不再崩溃；探针确认实际库路径与候选 SHA256，Gallium Build ID 为 `9655e407b21f062859570f90c2acd6e3a5c7b7a0`。原桌面继续运行。该测试使用 Nouveau render node 与 Tegra 包装层，不覆盖 native KMS 或物理面板；native Niri 验收仍未完成。见 [候选实机记录](diagnostics/2026-10-09-mesa-candidate-egl.json) 和 [Mesa fence 验收步骤](https://github.com/Pisces-Moze/mocha-moze-desktop/blob/codex/tegra-fence-regression/docs/MESA-FENCE.md)。

## 扬声器/麦克风：未解决
RT5671 0x1c在官方1.2V ldoen、PMIC32k门控、GPIO5mux、12.288MHz MCLK下NACK。
分离I2C读写与100kHz速率测试仍NACK，两颗TFA9890同总线revision0080可读。MTP0000并不证明校准缺失，因为完整DSP时序未运行。
官方TFA驱动和machine（I2S0→AIF1，AIF2→左右TFA、48k/16bit/stereo）已编译，不能据此称声卡可用。没有写MTP、绕过扬声器保护或播放未经校准的音频。
旧MIUI内核RAM实验白屏/无USB，保留日志也没有得到成功音频参考；用户反馈官方MIUI曾正常发声。

## 充电 UI 与按键
initramfs错误导致 /init未进入；ELF interpreter曾被copyfile写成0644，内核执行UI返回126。修正为0755并检查最终CPIO元数据。
充电target隔离桌面后logind仍处理电源键，长按重启：以systemd-inhibit接管handle-power-key，由UI返回10进桌面、20关机。
BC1.2识别DCP后2A输入，PC未知500mA，CDP1.5A；电池侧仍960mA/4.208V，2A输入不是2A电池实测。运行充电政策时实测约+0.85A桌面/+1A最小模式，温度正常。电量计跳变和完全关机充电状态机仍有改进空间。

## 视频、壁纸与 CUDA
2026-10-20 已安装单次静态切换的生命周期修复及严重资源压力释放／恢复策略；阈值触发实机检查确认播放器退出、VDE 挂起并恢复 Request 硬解。追加设置重载边界补丁也已通过回归并安装。多窗口真正遮挡判断、动态桌面 CPU 和交互卡顿仍未解决；播放器更新标志修正的短采样没有证明性能收益。弹窗／概览期间继续播放，保留透明及毛玻璃效果。

补齐 FFmpeg/libavcodec/MPV 后软件视频和 Firefox HTML5 通过。2026-10-18 的 VDE2 修复已带备份持久安装并通过普通启动，GStreamer 与 FFmpeg Request 的逐帧比较、正式壁纸插件的三轮前台全屏释放／恢复和弹窗／概览持续播放通过。内置 VDE 保持关闭，由桌面硬件服务显式校验并加载匹配模块。仍有 CPU 布局转换，只验证渐进式 CAVLC；浏览器硬解没有接通。频谱空闲修复和选择器桥接已安装，静态采样没有证明 CPU 显著下降，全屏恢复仍有显示丢帧，锁屏后的壁纸恢复与完整动态性能仍待优化。
Noctalia壁纸列表改为专用目录，数据文件安装后缩略图通过。
CUDA开发libcuda stub的cuInit仅返回-1；真实NVIDIA库依赖旧驱动ABI。Gdev有限Driver API修复代码上传/GPU引用/ARM缓存后257与8193整数计算通过。CUDA6.5libcudart仍error35（驱动版本不足），不能声称完整CUDA运行时支持。

## 2026-10-10 原生显示分段与启动时序

真实 Tegra render node 的候选 Mesa fence 测试已通过；修复后的背光模块成功加载，DRM connected/enabled。CPU framebuffer 与 GPU DMA-BUF/KMS 色块均只有背光、黑屏；GPU 测试虽完成 1800 次翻页约 29.99 FPS，物理扫描输出仍失败。随后恢复 native5 的 DSI-B 控制归属后色块可见，仅手动校正 A=0/B=768 后位置正常。首版视频 enable 前校正，以及第二版 enable 后等待 40 ms 校正，都仍物理黑屏；自动修复未通过，新内核关闭校正属性后也黑屏，而原始内核＋相同 native5 DTB 的可见色块已复现。原始组合手动校正后，GPU DMA-BUF/KMS 与候选 Mesa 下的 Niri＋终端画面均由用户确认正常；仍需手动校正，Noctalia、触控与长期运行未验收。原始驱动重建基线与此前成功内核仅有 34 字节构建元数据不同，机器指令相同；这次首次启动仍黑屏，但 DRM 关闭再开启后恢复可见，手动校正后的 GPU/Niri 画面正常。首次初始化状态/时序是当前排查方向，主动复位候选随后通过两次有效冷 RAM CPU/控制台与一次 GPU/Niri 自动分段验收，未手动改起点或做额外 DPMS 恢复。过早 MMIO 访问干扰的一轮已单独记录；完整会话、触控和默认安装仍待验收。暂不替换默认路径。见 [本轮记录](DIAGNOSTICS-2026-10-10.md)。
