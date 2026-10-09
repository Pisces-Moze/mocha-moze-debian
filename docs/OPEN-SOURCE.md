# 开源范围与源码审计

审计日期：2026-10-10。硬件验证仍以 [VALIDATION.md](VALIDATION.md) 的开发快照为准；此次补充源码不代表重新完成整套安装验收。

本项目编写或修改的引导、Linux 驱动、设备树、内核配置、桌面补丁、系统服务、充电策略和充电动画均公开源代码。项目自编代码采用 GPL-2.0-only；移植文件保留厂商版权、SPDX 和原许可证，第三方项目沿用其上游许可。不能用项目的 LICENSE 替第三方专有文件授予开源或再分发权。

## 五仓库的源码边界

| 仓库 | 可审查、修改和构建的内容 |
|---|---|
| [mocha-moze-linux](https://github.com/Pisces-Moze/mocha-moze-linux) | 完整 Linux 源码；`moze/source-overlay/` 同时列出板级修改；`moze/configs/`、`moze/dts/`、`moze/tools/` 包含配置、设备树与构建过程 |
| [mocha-moze-boot](https://github.com/Pisces-Moze/mocha-moze-boot) | `overlay/` 中的 U-Boot 板级、面板与双 DSI 修改，`configs/` 和 `tools/` 中的编译参数、Android 容器打包及 RAM 加载工具；未修改的上游按构建脚本指定 tag 获取 |
| [mocha-moze-drivers](https://github.com/Pisces-Moze/mocha-moze-drivers) | 背光、音频 machine/TFA 移植源码，触控失败路径存档，GPU/显示/I2C/CUDA 诊断源码，Gdev 补丁与固件提取说明 |
| [mocha-moze-desktop](https://github.com/Pisces-Moze/mocha-moze-desktop) | Niri/Smithay 补丁、Noctalia 配置和构建工具、会话服务、充电识别与限流策略、竖屏动画 C 源码；Niri/Noctalia 上游按脚本固定版本获取 |
| [mocha-moze-debian](https://github.com/Pisces-Moze/mocha-moze-debian) | rootfs、initramfs、USB 管理网络、存储安装工具、版本锁、参数索引、安装与回退文档 |

树内 Atmel 触控、Nouveau、brcmfmac、Palmas、BQ24190 等驱动在完整 Linux 仓库中；不能因为它们不在外置 drivers 仓库就认为缺少源码。外置 `.ko` 必须从对应源码针对同一内核 release 构建，不依赖本机构建机的私有模块文件。

本次补齐了 `diagnostics/charger-id-probe.c`、`diagnostics/read-framebuffer.c`、`cuda/probe-legacy-cuda.c` 和 `services/mocha-active-seat.c`。后者是历史会话诊断程序，固定 UID 1000，不是默认权限策略；现有安装脚本和 logind/polkit 才是安装配置的入口。帧缓冲读取程序也仅用于历史布局取证，不是桌面运行或原生 GPU 显示所需组件。

本次验证：前三个诊断程序用 `arm-linux-gnueabihf-gcc -O2 -Wall -Wextra` 编译为 ARM EABI5；active-seat helper 用构建主机的 C 编译器链接 libsystemd 编译通过（主机缺少 pkg-config 的 libsystemd 元数据，因此检查使用 `-l:libsystemd.so.0`）。未执行硬件探测、未重启平板。JSON/TOML/Python 语法、文档本地链接和凭据模式检查通过。

## 参数与可复现构建

[PARAMETERS.md](PARAMETERS.md) 按组件列出所有参数的源码入口；具体数值以锁定 commit 中的配置为准。使用 [INSTALL.md](INSTALL.md) 的五仓库构建顺序及 `manifests/repos.lock.json`，不要把不同开发候选的 DTS、内核和模块混装。

[`manifests/open-source-files.json`](../manifests/open-source-files.json) 记录本次公开的项目源码、配置、补丁及文档的 SHA256；完整未修改的 Linux 上游树由 Git commit 和来源记录标识。清单不包含自身，避免循环哈希。`kernel_overlay_matches_full_tree` 表示逐字节核对过 `moze/source-overlay/` 与 Linux 完整 Git 树中的对应文件。

Windows 本地可能采用 sparse checkout，因为上游 Linux 包含 NTFS 保留名称；远端 Git 仍有完整树。请在 Linux 的大小写敏感文件系统上正常克隆和构建，不能把 Windows 稀疏工作目录当作完整源码打包。

检出版本锁指定的仓库后，可在五仓库的父目录运行：

```sh
python3 mocha-moze-debian/tools/verify-source-inventory.py .
```

此命令检查清单中的文件是否缺失或变更。源码行尾应为 LF；有本地修改时哈希不匹配属于预期，它不会覆盖任何文件，也不代替编译和实机验证。

## 尚不能声称“整个设备无闭源依赖”

原厂 BootROM/最前级 bootloader/TOS、GK20A 微码、BCM4354 Wi-Fi/蓝牙固件、设备校准资产，以及旧 NVIDIA CUDA/L4T 用户态库有各自来源与许可。本项目没有这些专有组件的完整源码，也不冒称它们开源。提取路径、请求文件名和来源核对见 [固件说明](https://github.com/Pisces-Moze/mocha-moze-drivers/blob/main/firmware/README.md) 与 [SOURCES.md](../SOURCES.md)。CUDA 的仓库引导 `.deb` 不能代替现代 Linux 内核驱动源码或兼容性证明。

公开的是项目设置的 GPIO、时序、电压范围、限流、显示布局等参数；SSH/Wi-Fi 凭据、设备 MAC、原始 NVRAM、TFA MTP 校准值和分区备份属于个人设备数据，不放进公开仓库。必要身份数据由安装者从自己的设备提供。

## 已公开实现不等于已完成硬件适配

扬声器/麦克风链路、蓝牙、摄像头、硬件视频编解码和完整 CUDA Runtime 仍未完成。原生 Tegra/GPU 色块出图已有实机记录，但不能据此宣称 Niri 桌面已全面消除显存读回和 CPU 搬运；默认显示路径仍有性能限制。请对照 [STATUS.md](STATUS.md)、[ISSUES.md](ISSUES.md) 和各驱动 README，不把编译成功、服务启动或 DRM 翻页成功当作硬件功能完成。
