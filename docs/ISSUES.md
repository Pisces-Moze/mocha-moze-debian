# 已遇到的问题与实现思路

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

## Niri native SIGSEGV：未解决
block-linear framebuffer的atomic TEST_ONLY返回EINVAL，随后fallback启动，但Mesa/Gallium内部跳到PC=0；实际GDB捕获LR并匹配库Build ID。不是凭“黑屏”猜测。
Mesa 25.0.7-2+deb13u1 Build ID fd7dcad10de8c89211ebe69ae8c8dda302f047d0，返回偏移0xd645bc，匹配 Debian 调试符号为 `tegra_fence_server_sync`，`src/gallium/drivers/tegra/tegra_context.c:834`。目前只定位到调用点，仍需确认空函数指针的来源，不能把定位称为修复。
CONFIG_COREDUMP=y但CONFIG_ELF_CORE关闭，第一次core捕获没有生成文件；改用ARM gdbserver抓栈。
后续需要修复缺失的驱动回调/缓冲区协作、验证真实native桌面，再测DMA-BUF、CPU_PREP和copy；当前不能标注Niri zero-copy完成。

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

## 蓝牙：现代内核可发现与配对（2026-11-14，3 GB 改装机）
控制器是 BCM4350C0（组合芯片报 BCM4354），UART HCI。三个独立问题：① 缺 `brcm/BCM4354.hcd`，MIUI 的 `BCM4350C0.hcd` 改名即可，mainline btbcm 加载成功（build 0000→0367）；② 固件在 rootfs 挂载前就被请求，开机那次 probe 必然失败，需在服务里 unbind/bind `serial0-0` 重新 probe；③ 控制器默认地址是占位符（首字节带组播位，手机直接丢弃），用 Broadcom `0xFC01` 写 `00:90:4C:16:70:02`，`hciconfig hci0 reset` 让内核重读，且必须排在 bluetoothd 启动之前。
实机：手机可搜到 “mocha” 并配对。未验证 BT 音频与 HID 外设。

## 扬声器：RT5671 + 双 TFA9890 发声通过
此前记录 RT5671 0x1c NACK。本机最终方案是 out-of-tree 的 RT5671 board 驱动（`register_codec=1`）、I2S probe、DATA pin、TFA9890 与 runtime card 六个模块，加上从本机提取的 TFA 校准/预设写入 `/lib/firmware/mocha`。声卡注册为 `Mocha Speakers`，TFA 日志出现 Factory calibration and DSP protection ready、output unmuted；raw PCM 与 PipeWire 两条路径都由用户确认发声。
未验证耳机检测与麦克风；模块必须针对同一 kernelrelease 编译。

## CPU DVFS：native-runtime 上通过 DFLL monitor 校验
`native-runtime` 配置 + DTS 里 DFLL `status = "okay"` 后，`cpufreq-dt` 出现 20 档（204 MHz–2116 MHz），`dfllCPU_out` 成为 `cpu_g` 的 parent，`vdd-cpu` 随频率变化（204 MHz→900 mV）。
monitor 校验：请求 1122 MHz 读回 1189 MHz；请求 1428 MHz 读回 1511 MHz。独立时间基准（不读 CCF）：同一段 4,000,000 次乘加在 204 MHz 下 14.785 s、1530 MHz 下 1.859 s（7.95×）。
边界：1530 MHz 四核满载 30 s 稳定（76–85 °C）；2014 MHz 持续满载会挂；2116 MHz 一上负载即挂。上限取 1530 MHz，默认仍不启用。

## 3 GB 改装机：native-runtime 需要 CONFIG_ARM_LPAE
`moze/configs/native-experimental.config` 里 `CONFIG_ARM_LPAE` 关闭，`native-runtime` 直接继承，导致 3 GB 硬件改装机静默只拿到 2 GB（DT 两个 bank 都在，内核丢弃 4 GB 以上那段；`MemTotal` 2,001,992 kB）。给 `native-runtime.fragment` 补 `CONFIG_ARM_LPAE=y` 后恢复 2,976,304 kB。
注意：改 LPAE 这类配置后必须重装整套模块，旧 `.ko` 能被加载但 nouveau 会在 `nouveau_channel_new` 崩溃（先报 `unable to map PRI`）。


## 充电/桌面环境的使用坑
`systemctl reboot` 偶尔停在 `Rebooting.` 不硬件复位（本机两次），需长按电源 15 秒；可靠重启用 `echo b > /proc/sysrq-trigger`。
往 `/` 解包 payload 时必须用 `tar --keep-directory-symlink`，否则包内的顶层 `lib/` 会把 usrmerge 的 `/lib -> usr/lib` 替换成真实目录，动态加载器失效、系统启动循环（本机遇到两次）。
