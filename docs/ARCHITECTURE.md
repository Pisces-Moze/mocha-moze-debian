# 设计与联动

## 启动链

原厂 Tegra bootloader → LNX 分区中的 Android boot.img 容器 → 32 位 U-Boot → eMMC APP 内 `/boot/uImage-desktop`、DT、initramfs → Debian systemd。
保留原厂 bootloader/TOS/SOS。U-Boot 不是写进 SoC BootROM，也没有取代最前级签名启动链。
临时 `fastboot boot` 只把容器加载到 RAM；持久化阶段仅在验证 Debian 能从 APP 启动后写 LNX，并回读。
U-Boot 禁止 MMC 写、Fastboot flash、saveenv、GPT 编辑；安装写操作通过受控 RAM Linux 完成。

## 内核/驱动边界

Linux 仓库包含板级集成修改（TLK 复位接口、USB/PMIC、内存早期诊断、Tegra DRM 双 DSI公式及面板）。
drivers 仓库包含外置模块（LP8556、TFA98XX、ASoC machine）及其实验状态，必须针对同一 kernelrelease 构建。
DTS stable 继承已初始化的屏幕给 simpledrm；native 使用 Tegra DRM/双 DSI，仍是实验。硬件枚举顺序不同，GPU renderD 节点不能写死。

## 用户空间

桌面层由 Niri、Noctalia、NetworkManager、BlueZ、PipeWire/WirePlumber、UPower、logind 和 polkit 协作。
“菜单能显示”不代表对应硬件已可用：没有 ALSA card 时 PipeWire 本身运行也没有扬声器；BlueZ 服务启动也不代表 UART/HCI 初始化成功。
默认桌面横屏 `transform 90`、scale 1.5，触控绑定对应输出；充电 UI 直接画到 framebuffer，独立竖屏和独立最小 target。

## 产物契约

kernel构建目录: `uImage`、`Image`、`mocha.dtb`、`modules/`、`.config`、`SHA256SUMS`；复制进rootfs时改为`/boot/uImage-desktop`和`/boot/mocha-desktop.dtb`。`kernelrelease`由make输出，保存日志并与模块目录核对。
drivers: 针对该 release 的 `.ko`；desktop: 本机 ARMhf ELF、配置/服务、充电 UI；boot: `.img` 和 `.config`；debian: 私有密钥之外的 rootfs ext4/manifest。
每次发布生成 SHA256SUMS。版本锁固定源码，产物哈希固定具体构建，两者不可替代。
