# 参数与实现入口

本表索引公开的运行参数和驱动实现，不另建一份与源码脱节的隐藏配置。完整安装流程见 [INSTALL.md](INSTALL.md)，开源边界见 [OPEN-SOURCE.md](OPEN-SOURCE.md)。所有路径相对于对应仓库；请先用 `manifests/repos.lock.json` 获取同一组源码。

| 组件 | 仓库与入口 | 应检查的参数/实现 |
|---|---|---|
| 引导容器与 RAM 布局 | boot：`tools/pack-android.py`、`tools/load-ram.py`、`overlay/board/xiaomi/mocha/` | Android header、U-Boot entry、内核/DT/initramfs 地址、启动环境与加载命令；文件名以实际目录为准 |
| U-Boot 功能开关 | boot：`configs/mocha_defconfig.full`、`tools/build.sh` | 禁用 MMC 写入、Fastboot flash、saveenv、GPT 编辑；双 DSI 面板复位、初始化、交接在 `overlay/drivers/video/tegra/` |
| Linux 编译配置 | linux：`moze/configs/`、`moze/tools/build.sh` | stable/native/SMP 配置、ARCH/CROSS_COMPILE、kernelrelease、模块与 DT 构建 |
| 内核命令行与设备枚举 | linux：`moze/dts/stable-desktop.dts`、`native-experimental.dts`、`moze/source-overlay/arch/arm/boot/dts/` | reserved-memory、各总线、clock/reset、GPIO、regulator 约束与 phandle；最终 bootargs 同时检查 boot 环境 |
| 四核启动 | linux：`moze/source-overlay/arch/arm/` | Tegra/TLK 安全复位兼容接口、启动路径与早期诊断；引导 `maxcpus=4`，不是超频参数 |
| PMIC/充电/电量计 | linux：设备树及 `moze/source-overlay/drivers/regulator/`、`drivers/power/` | Palmas 控制模式、电压约束、BQ24192/BQ27520 驱动与供电关联；不能只抄一个电流数值 |
| USB 会话检测 | linux：`moze/source-overlay/drivers/usb/` | Tegra PHY、ChipIdea、VBUS/PMIC 会话交接；debian：`rootfs/mocha-usb`、`ramdisk/init-*` 设置 RNDIS/SSH 网络 |
| 触控 | linux：树内 Atmel maXTouch 驱动和 stable DTS；drivers：`touch/` | 本机 Atmel 1664T 地址 0x4a、IRQ GPIO143、reset GPIO84；Synaptics 仅为失败路径存档，不替换当前 Atmel |
| 背光 | drivers：`backlight/mocha_miui_backlight.c`；desktop：`tools/install-session.sh`、`config/` | MIUI LP8556 寄存器初始化、亮度映射、sysfs 权限与 Noctalia 绑定 |
| 音频 | drivers：`audio/` | RT5671 machine、TFA9890 路由、I2C/供电/复位/DSP 加载与 MTP 保护；未完成发声 |
| GPU/原生双 DSI | linux：`moze/source-overlay/drivers/gpu/drm/`；drivers：`diagnostics/native-dmabuf-scanout-v2.c` | Tegra DSI 时钟/校准/面板时序、DRM/GBM/EGL、DMA-BUF 导入、格式/stride/modifier 与翻页；显示节点动态识别 |
| CUDA | drivers：`cuda/` | Gdev 补丁、Driver API/内核探测、PTX、旧 libcuda 加载检查；完整 Runtime 未通过 |
| 桌面与会话 | desktop：`config/niri.kdl`、`config/noctalia.toml`、`patches/`、`tools/`、`services/` | 横屏 transform、scale、触控输出映射、损伤区域补丁、NetworkManager/BlueZ/PipeWire/UPower/logind/polkit 的服务配置 |
| 关机充电 | desktop：`charging/` | BC1.2 检测、输入电流策略、温度/健康约束、systemd target/generator、按键退出、竖屏绘制和动画时序 |
| 存储安装 | debian：`manifests/`、`tools/storage.sh`、`ramdisk/init-*` | 分区身份、尺寸、只读核对、APP/LNX 写入与回读；安装者自己的布局才是写入依据 |

## 已使用的关键值

内核名为 **mocha moze linux 6.12.111-moze.1**；实际 release 是 `6.12.111-moze.1`，native 是 `6.12.111-moze.1-native`。模块 vermagic 和安装目录必须与 `make kernelrelease` 相同。

引导内存布局：uImage header `0x80007fc0`、Image load/entry `0x80008000`、initramfs `0x88000000`、DT `0x8c000000`；U-Boot text base `0x80a00000`。默认参数包含 `mem=1700M maxcpus=4`、APP 根分区、串口与屏幕 console、`clk_ignore_unused regulator_ignore_unused`，其作用和限制必须结合 DTS 保留区及引导源码检查。不要保留旧候选的 initramfs 地址。

面板为 1536×2048 双 DSI；默认桌面横屏 `transform 90`、scale 1.5，充电动画独立竖屏。历史帧缓冲取证程序固定读取 `0xf1700000`、1536×2048×2 字节，只适用于其原始布局，不代表所有启动候选的地址/格式。

充电策略区分 **输入电流上限** 和 **电池充电电流**。公开脚本对识别出的 DCP 使用 2,000,000 µA 输入上限，CDP 1,500,000 µA，电脑/未知来源 500,000 µA；温度低于 0°C 或达到 45°C、health 非 Good 时收紧策略。以 `charging/mocha-charge-policy.py` 和实际 power_supply 属性为准，2 A 充电器铭牌不证明电池始终净流入 2 A。驱动寄存器编码、终止电压和电池电流设置在驱动/DTS 中，不能把输入上限用于替换它们。

未公开个人凭据和设备独有校准值不是隐藏驱动参数；它们的来源与安装输入见 [OPEN-SOURCE.md](OPEN-SOURCE.md)。本工程未启用 CPU/GPU 超频。
