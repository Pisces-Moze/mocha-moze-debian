# 已遇到的问题与实现思路

## 2026-10-16 持久安装与充电启动

运行系统已提升为持久 `native-runtime` 并确认普通启动。充电动画方向、短暂拔插线重新亮屏，以及插电按住电源直接进桌面均通过本机用户观察；最后一项同时记录到 U-Boot 提前采样为 held、Linux 桌面请求为 1、充电服务未启动。APP 尚未扩容，整盘离线备份和 3 GiB 迁移仍待完成；其他外设任务依用户顺序后置。原厂前级短按门控、完整频率／电压曲线和长期压力测试不能据此标为解决。见 [本次证据](DIAGNOSTICS-2026-10-16.md)。

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
补齐FFmpeg/libavcodec/MPV后软件视频和FirefoxHTML5通过，硬件解码未完成：Tegra124 VDE非标准tile布局尚未提供完整格式。
Noctalia壁纸列表改为专用目录，数据文件安装后缩略图通过。
CUDA开发libcuda stub的cuInit仅返回-1；真实NVIDIA库依赖旧驱动ABI。Gdev有限Driver API修复代码上传/GPU引用/ARM缓存后257与8193整数计算通过。CUDA6.5libcudart仍error35（驱动版本不足），不能声称完整CUDA运行时支持。

## 2026-10-10 原生显示分段与启动时序

真实 Tegra render node 的候选 Mesa fence 测试已通过；修复后的背光模块成功加载，DRM connected/enabled。CPU framebuffer 与 GPU DMA-BUF/KMS 色块均只有背光、黑屏；GPU 测试虽完成 1800 次翻页约 29.99 FPS，物理扫描输出仍失败。随后恢复 native5 的 DSI-B 控制归属后色块可见，仅手动校正 A=0/B=768 后位置正常。首版视频 enable 前校正，以及第二版 enable 后等待 40 ms 校正，都仍物理黑屏；自动修复未通过，新内核关闭校正属性后也黑屏，而原始内核＋相同 native5 DTB 的可见色块已复现。原始组合手动校正后，GPU DMA-BUF/KMS 与候选 Mesa 下的 Niri＋终端画面均由用户确认正常；仍需手动校正，Noctalia、触控与长期运行未验收。原始驱动重建基线与此前成功内核仅有 34 字节构建元数据不同，机器指令相同；这次首次启动仍黑屏，但 DRM 关闭再开启后恢复可见，手动校正后的 GPU/Niri 画面正常。首次初始化状态/时序是当前排查方向，主动复位候选随后通过两次有效冷 RAM CPU/控制台与一次 GPU/Niri 自动分段验收，未手动改起点或做额外 DPMS 恢复。过早 MMIO 访问干扰的一轮已单独记录；完整会话、触控和默认安装仍待验收。暂不替换默认路径。见 [本轮记录](DIAGNOSTICS-2026-10-10.md)。
