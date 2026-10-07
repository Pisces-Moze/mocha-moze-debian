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
