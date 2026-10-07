# Mocha Moze Debian

> 把 Debian armhf Linux 装到小米平板 1（A0101，代号 Mocha，NVIDIA Tegra124）上的五仓库工程总入口。

[![License: GPL-2.0-only](https://img.shields.io/badge/License-GPL--2.0--only-blue.svg)](LICENSE)

## 简介

小米平板 1 出厂运行 Android，厂商没有为它提供 Linux 桌面发行版。这个工程整理出一条可复现的安装路线：源码从哪里来、按什么顺序构建、怎样先在内存里临时启动验证，确认无误后再写入内置存储，以及每一级失败之后怎么退回去。

工程拆成五个仓库，本仓库是总入口，负责版本锁定、根文件系统、RAM 引导安装器、分区核对和全部文档，内核、U-Boot 与驱动的源码放在另外四个仓库。当前发布是 2026-10-07 的源码开发快照，不是所有外设都能用的成品安装盘；默认显示与原生显示实验是两条分开的路径。内核人类名称是 mocha moze linux 6.12.111-moze.1，`UTS_RELEASE` 与模块目录用 `6.12.111-moze.1`（空格只出现在项目名称里，不进入 uname），native 实验内核的 release 是 `6.12.111-moze.1-native`。`manifests/repos.lock.json` 里的 `new_brand_end_to_end_tested` 为 `false`：改名之后的完整安装还没有端到端实机验收过。完整安装路线见 [INSTALL.md](docs/INSTALL.md)，首次阅读请同时看 [状态表](docs/STATUS.md) 和 [回退](docs/RECOVERY.md)。

## 硬件背景与适用机型

| 项目 | 本机情况 |
|---|---|
| 机型 / 代号 | 小米平板 1 A0101 / Mocha；Tegra K1（Tegra124），ARMv7 32 位，GK20A/NVEA GPU，1536×2048 双 DSI 面板 |
| 存储与分区 | 16 GB eMMC，identity `016GE2`；APP=`mmcblk0p26`，起始 524288、2612431 个 512 字节扇区（1337564672 字节）；LNX=`p22`，起始 393216、40960 扇区；UDA=`p29` |
| 触控 | Atmel maXTouch 1664T，I2C 0x4a，IRQ GPIO143，reset GPIO84 |
| 电源、背光、音频与无线 | Palmas / TPS65913；BQ24192 充电（用 Linux 通用 bq24190 驱动）；电量计 BQ27520-G4；背光 LP8556；RT5671 加左右 TFA9890，主机时钟 12.288 MHz，功放地址 0x34/0x37，codec 0x1c；BCM4354 为 Wi-Fi/蓝牙组合芯片 |

不适用于 Mi Pad 2/3/4，也不适用于 ARM64。

触控存在批次差异：本机实际是 Atmel maXTouch 1664T，最初试 Synaptics DSX 没有响应，后来拿它与官方 Atmel with_dummy 配置比对，差异为零，控制器固件也没有升级过。其他批次可能使用别的触控，「官方源码里有 Synaptics」不能当作强行刷写 Synaptics 固件的理由。除触控批次之外还有容量差异：16 GB 的 APP 只有 1337564672 字节，32 GB 版本或其他 GPT 布局必须先调整安装计划、initramfs 中的布局检查及引导根分区再动手。本机的 PARTUUID、MAC、密钥和校准数据都不要复制到别处。

## 项目家族

| 仓库 | 负责内容 |
|---|---|
| [mocha-moze-debian](https://github.com/Pisces-Moze/mocha-moze-debian) | 总入口、版本锁、rootfs、RAM 引导安装、分区核对和文档 |
| [mocha-moze-boot](https://github.com/Pisces-Moze/mocha-moze-boot) | U-Boot 2026.07 覆盖源码、Android 容器、双 DSI 冷启动交接 |
| [mocha-moze-linux](https://github.com/Pisces-Moze/mocha-moze-linux) | Debian Linux 6.12.111 完整源码基线及 Mocha 修改、配置和 DTS |
| [mocha-moze-drivers](https://github.com/Pisces-Moze/mocha-moze-drivers) | MIUI 背光/音频移植、固件提取说明、GPU/CUDA 诊断和驱动实验 |
| [mocha-moze-desktop](https://github.com/Pisces-Moze/mocha-moze-desktop) | Niri/Smithay 补丁、Noctalia 配置、服务、竖屏充电界面 |

```
# tools/workspace.py fetch 生成的布局
mocha-workspace/
  mocha-moze-debian/       # docs/ tools/ manifests/
  mocha-moze-boot/         # overlay/ configs/ tools/
  mocha-moze-linux/        # Linux 原目录 + moze/configs,dts,tools
  mocha-moze-drivers/      # backlight/ audio/ diagnostics/ firmware/
  mocha-moze-desktop/      # config/ patches/ charging/ tools/
  artifacts/               # 自己构建的产物，不提交 Git
```

## 架构与组件

启动链是：原厂 Tegra bootloader → LNX 分区中的 Android boot.img 容器 → 32 位 U-Boot → eMMC APP 内 `/boot/uImage-desktop`、DT、initramfs → Debian systemd。原厂 bootloader、TOS、SOS 都保留，U-Boot 不写进 SoC BootROM，也没有取代最前级的签名启动链。临时 `fastboot boot` 只把容器加载到 RAM；持久化阶段要等 Debian 能从 APP 启动验证通过之后才写 LNX，并回读比对。线上跑的 U-Boot 禁用了 MMC 写、Fastboot flash、saveenv 和 GPT 编辑，所有写操作由受控的 RAM Linux 完成；其 text base 是 `0x80a00000`，Android legacy header 保留 Mocha 已验证的加载字段。内核与驱动按仓库分边界：linux 仓库包含板级集成修改（TLK 复位接口、USB/PMIC、内存早期诊断、Tegra DRM 双 DSI 公式与面板），drivers 仓库是外置模块（LP8556、TFA98XX、ASoC machine）及其实验状态，必须针对同一个 kernelrelease 构建。DTS 分两套，stable 把已初始化的屏幕交给 simpledrm，native 走 Tegra DRM/双 DSI 且仍是实验；硬件枚举顺序会变，GPU renderD 节点不能写死。

用户空间由 Niri、Noctalia、NetworkManager、BlueZ、PipeWire/WirePlumber、UPower、logind 和 polkit 协作。菜单能显示不等于对应硬件可用：没有 ALSA card 时 PipeWire 照常运行但没有扬声器，BlueZ 服务启动也不代表 UART/HCI 初始化成功。默认桌面横屏 `transform 90`、scale 1.5，触控绑定到对应输出；充电界面直接画到 framebuffer，用独立的竖屏和独立的最小 target。公开仓库采用复制、筛选和脱敏整理，不删除历史原件；目录名里带 candidate 不代表文件就是实际测试版本，构建脚本可能用 trap 恢复源码。

| 路径 | 作用 |
|---|---|
| `tools/workspace.py` | 读 `manifests/repos.lock.json`，克隆缺失仓库并检出锁定 commit；工作区有未提交改动时中止 |
| `tools/build-rootfs.sh`、`tools/build-initramfs.sh` | 前者 debootstrap 生成 trixie/armhf 核心 rootfs 并装入内核产物、SSH 授权与 USB 服务；后者生成 busybox initramfs，`install` 模式带 Dropbear 与 `ramdisk/init-install`，`emmc` 模式用 `ramdisk/init-emmc` |
| `tools/make-app-image.sh`、`tools/storage.sh` | 前者按 APP 精确字节数生成 ext4 镜像并算哈希；后者在 RAM 安装器里读计划、写 APP/LNX 并回读校验 |
| `ramdisk/init-install`、`ramdisk/init-emmc` 与 `rootfs/mocha-usb`、`rootfs/mocha-usb.service`、`manifests/*.json` | RAM 安装环境先把 eMMC 锁成只读再起 RNDIS 与 key-only SSH；emmc 模式核对 APP 分区身份后挂载并 switch_root 到 Debian；装进目标系统的 RNDIS 管理网络（`Before=ssh.service`）；源码版本锁与来源记录 |

版本锁和产物哈希是两件事：`repos.lock.json` 固定四个仓库的 commit，`SHA256SUMS` 固定某一次具体构建，前者代替不了后者。本快照锁定的是 boot `7163a222b93ed05ba97e6f0d725bbec348f48938`、linux `a86530c19fbda5d7b70b6cc22d1f8f429cd9ae59`、drivers `2390e8bbe0765b3db9c4656c5e0e957cf4a4f8dc`、desktop `45a1c7360adea09e4ed91cb729a6af891d339e68`。

## 部署过程

下面所有命令都以 `mocha-workspace` 为当前目录，构建顺序是 kernel → 外置驱动 → U-Boot/容器 → rootfs/桌面 → RAM 验证 → APP → LNX。前置条件：Debian 13 amd64 虚拟机或实体机作构建主机，至少 20 GB 空闲空间；Windows 只用来跑原厂 Fastboot 和 SSH，完整 Linux 源码要在大小写敏感的文件系统上构建；平板电量充足。构建主机上的 sudo 只用于临时 rootfs 和 loop 挂载，不在运行中的平板上执行。

### 1. 主机工具与工作区

```sh
sudo apt update && sudo apt install git python3 build-essential bc bison flex libssl-dev libelf-dev gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf binutils-arm-linux-gnueabihf device-tree-compiler u-boot-tools debootstrap qemu-user-static binfmt-support dropbear-bin e2fsprogs dosfstools cpio gzip xz-utils rsync curl openssh-client adb fastboot pkg-config meson ninja-build clang libclang-dev cmake
git clone https://github.com/Pisces-Moze/mocha-moze-debian.git && cd mocha-moze-debian && python3 tools/workspace.py fetch --dest ../mocha-workspace
cd ../mocha-workspace && mkdir -p artifacts && ssh-keygen -t ed25519 -f artifacts/developer-key
```

`workspace.py fetch` 克隆缺失仓库，用 `git fetch origin <commit>` 加 `checkout --detach` 检出锁定版本，逐个打印 HEAD；某仓库有未提交改动时报 `Uncommitted work:` 并退出，不会覆盖你的工作；它同时把总入口仓库自身复制进 `mocha-workspace`。只看当前锁在哪一版用 `python3 tools/workspace.py status --dest ../mocha-workspace`。私钥只放本地：`artifacts/developer-key.pub` 是 RAM SSH 的授权输入，每次生成 RAM 镜像都会新建 Dropbear host key，构建输出会列出指纹，连接时记到自己的 `known_hosts`。

### 2. 内核、外置驱动、U-Boot 与 rootfs

```sh
cd mocha-moze-linux && bash moze/tools/build.sh stable ../artifacts/kernel
cd ../mocha-moze-drivers && bash tools/build-backlight.sh ../mocha-moze-linux ../artifacts/kernel
cd .. && bash mocha-moze-boot/tools/build.sh artifacts/uboot
python3 mocha-moze-boot/tools/pack-android.py artifacts/uboot/u-boot-dtb.bin artifacts/uboot/u-boot artifacts/mocha-uboot.img
sudo bash mocha-moze-debian/tools/build-rootfs.sh artifacts/rootfs artifacts/developer-key.pub artifacts/kernel
sudo bash mocha-moze-debian/tools/build-initramfs.sh artifacts/rootfs artifacts/developer-key.pub artifacts/ram-install.cpio.gz install
sudo bash mocha-moze-debian/tools/build-initramfs.sh artifacts/rootfs artifacts/developer-key.pub artifacts/initramfs.cpio.gz emmc && sudo cp artifacts/initramfs.cpio.gz artifacts/rootfs/boot/initramfs.cpio.gz
sudo install -d artifacts/rootfs/usr/lib/modules/6.12.111-moze.1/extra && sudo install -m644 mocha-moze-drivers/backlight/mocha_miui_backlight.ko artifacts/rootfs/usr/lib/modules/6.12.111-moze.1/extra/
sudo depmod -b artifacts/rootfs 6.12.111-moze.1 && sudo bash mocha-moze-debian/tools/make-app-image.sh artifacts/rootfs artifacts/debian-app.img 1337564672
```

- 内核输出 `uImage`、`Image`、`mocha.dtb`、`modules/`、`SHA256SUMS`，release 为 `6.12.111-moze.1`；`kernelrelease` 由 make 输出，要保存日志并与模块目录核对；稳定设备树来自最终实测配置，已去掉设备私有身份和旧 initramfs 地址。外置模块必须用这一份内核构建目录的头文件和 `Module.symvers`，不要混用不同内核 release 的 `.ko`，背光模块要放进新内核自己的模块目录而不是原机旧 release。音频模块不在默认安装中启用，因为还没有完整声卡；固件要自己提取，见 drivers 仓库的 `firmware/README.md`，无线 NVRAM 不能使用别人的 MAC。
- U-Boot 的 `build.sh` 与 `pack-android.py` 在 boot 仓库：`build.sh` 浅克隆上游 `v2026.07` 并用 `git describe --tags --exact-match` 断言 tag，覆盖 `overlay/` 后把 `configs/mocha_defconfig.full` 当作 `.config`，编译前逐项断言 `MMC_WRITE`、`EXT4_WRITE`、`FASTBOOT_FLASH`、`CMD_SAVEENV`、`CMD_GPT`、`ENV_IS_IN_MMC` 都未开启，命中即失败；`pack-android.py` 要求 payload 是 ARM32 ELF 且 entry 为 `0x80a00000`，再按 page 2048 拼出 `ANDROID!` 容器并写出同名 `.json` 元数据（含 sha256）。
- `build-rootfs.sh` 要求 root 运行、目标目录尚不存在、公钥是 `ssh-ed25519` 或 `ssh-rsa`，第二段在 `qemu-arm-static` 下执行；生成的模块目录 release 必须等于 `6.12.111-moze.1`，否则退出。rootfs 写入 `/etc/mocha-internal-debian` 标记、`LABEL=mocha-debian` 的 fstab、新生成的 SSH host key，并启用 `ssh.service`、`mocha-usb.service`、`NetworkManager.service`。
- `make-app-image.sh` 的第三个参数必须是 APP 分区精确字节数 1337564672，且 `artifacts/rootfs/boot/initramfs.cpio.gz` 必须已存在；ext4 关闭 64bit、metadata_csum 和 orphan_file 以保持已测试 U-Boot 的只读加载兼容性，`e2fsck -fn` 后写出 `.img` 与 `.img.sha256`。生成镜像前把自己提取的必要固件放进 `artifacts/rootfs/usr/lib/firmware/`，尤其是 GK20A 微码和 BCM4354 无线文件；没有无线固件时仍可先走 USB SSH。核心 rootfs 是 Debian 13/trixie armhf，APP 保持小型系统，大型桌面与数据放到自己备份检查过的 UDA，或在完成 GPT 研究后另行扩容，本项目没有替你重分区。

### 3. 只在 RAM 里临时运行

```sh
# 平板按电源＋音量减进入原厂 Fastboot
fastboot devices
fastboot -s YOUR_SERIAL boot artifacts/mocha-uboot.img
# APP 里还没有 Debian 时：引导失败后 U-Boot 进 USB Fastboot，先核对 getvar all 与产品识别
python3 mocha-moze-boot/tools/load-ram.py --serial YOUR_UBOOT_SERIAL --kernel artifacts/kernel/uImage --dtb artifacts/kernel/mocha.dtb --initrd artifacts/ram-install.cpio.gz
# 进入 RAM 后核对：PID1、只读锁与 eMMC 挂载状态
ssh -i artifacts/developer-key root@172.31.124.2
cat /proc/1/comm                  # 应为 init，不是已安装系统的 systemd
cat /sys/class/block/mmcblk0/ro   # 应为 1
cat /proc/mounts                  # eMMC 无挂载
```

加载器把数据切成 1 MiB 固定大小传输块、末块补零、拷贝到 RAM 后启动，不执行 flash；旧的非固定尾块曾卡住，遇到超时回原厂 Fastboot 重试，不要继续使用不完整的 RAM 数据。RAM 里 `mmcblk0` 被锁成只读，锁不上时 `init-install` 拒绝开放远程访问；内核通过 USB RNDIS 提供 172.31.124.2/30，主机是 172.31.124.1，Windows 可能要装 USB RNDIS 驱动，Linux 可以手工给对应网卡配地址，DHCP 不提供默认路由。

### 4. 备份并保存分区计划

```sh
scp -O -i artifacts/developer-key mocha-moze-debian/tools/storage.sh root@172.31.124.2:/tmp/ && ssh -i artifacts/developer-key root@172.31.124.2 'sh /tmp/storage.sh plan > /tmp/layout.env' && scp -O -i artifacts/developer-key root@172.31.124.2:/tmp/layout.env artifacts/
ssh -i artifacts/developer-key root@172.31.124.2 'dd if=/dev/mmcblk0 bs=512 count=2048' > artifacts/gpt-prefix.bin
ssh -i artifacts/developer-key root@172.31.124.2 'dd if=/dev/mmcblk0p22 bs=1048576' > artifacts/LNX-before.img
ssh -i artifacts/developer-key root@172.31.124.2 'dd if=/dev/mmcblk0p26 bs=1048576' > artifacts/APP-before.img && sha256sum artifacts/*before.img artifacts/gpt-prefix.bin > artifacts/backup.sha256
```

在 RAM Linux 里也可以用 `lsblk -o NAME,SIZE,PARTLABEL,PARTUUID,MOUNTPOINTS` 核对一遍（BusyBox 环境可以读 sysfs 或自己装工具）。`storage.sh plan` 要求在 RAM 安装器里、PID1 是 `init`、eMMC 存在且未挂载、磁盘处于只读，输出自己的 CID、`DISK_SECTORS` 以及 APP/LNX 的起点与扇区数；工具保存的是你这台设备的 CID 和布局，不使用维护者设备的布局哈希。`gpt-prefix.bin` 只是前 2048 个扇区，不是完整的 GPT 灾难恢复副本，GPT 末尾和 UDA 中的个人数据备份也要自己完成；原始镜像和 `layout.env` 只属于你，不提交 Git。

### 5. 写 APP、回读、从内置存储临时启动

确认 `layout.env` 是刚从那台设备读出的，APP/LNX 与本仓库记录的 16 GB 布局一致。先传镜像并比较哈希，空间不足时不能截断上传；RAM 的 `/tmp` 就在 initramfs 根目录，不另挂默认半内存大小的 tmpfs，APP 镜像约 1.25 GiB，上传前确认没有桌面在运行且 RAM 仍够用。写 APP 这一步会删除 APP 里的旧系统内容。

```sh
scp -O -i artifacts/developer-key artifacts/debian-app.img artifacts/layout.env root@172.31.124.2:/tmp/ && sha256sum artifacts/debian-app.img && ssh -i artifacts/developer-key root@172.31.124.2 'sha256sum /tmp/debian-app.img'
ssh -i artifacts/developer-key root@172.31.124.2 'sh /tmp/storage.sh write APP /tmp/debian-app.img /tmp/layout.env REPLACE_APP'
# 回到原厂 Fastboot 再引导一次：这次 U-Boot 读 APP 自己的 /boot 三个文件，不再传 RAM 内核
fastboot boot artifacts/mocha-uboot.img
ssh -i artifacts/developer-key root@172.31.124.2 'cat /proc/1/comm; uname -r; cat /sys/devices/system/cpu/online; findmnt /; systemctl --failed'
```

`storage.sh write` 依次核对 RAM PID1、设备 CID、磁盘容量、分区起点与扇区数、无挂载，只接受本快照记录的布局（APP `524288:2612431`，LNX `393216:40960`）；APP 镜像必须与分区容量完全相等，写入用 `dd` 加 `bs=1048576 conv=fsync`，写完回读 SHA256 比对，不一致直接失败，结束时把磁盘和分区重新设回只读。它不改 GPT、TOS、SOS、UDA。首启结果应为 systemd、`6.12.111-moze.1`、`0–3`、根分区是 APP，而且必须实际看到双侧正常画面，不能只看日志返回成功。

### 6. 写 LNX 与后续步骤

从 APP 临时启动验证通过后，回到只读 RAM 安装环境（重新 Fastboot 临时启动并加载 ram-install）：

```sh
scp -O -i artifacts/developer-key artifacts/mocha-uboot.img artifacts/layout.env root@172.31.124.2:/tmp/
ssh -i artifacts/developer-key root@172.31.124.2 'sh /tmp/storage.sh write LNX /tmp/mocha-uboot.img /tmp/layout.env REPLACE_LNX'
```

`storage.sh write LNX` 只写镜像长度并验证前缀，不清空整个分区。之后普通关机、按电源键开机，至少重复两次冷启动，检查四核、USB 和左右屏幕；无法自动进入时用原厂 Fastboot 加载已验证的临时 U-Boot，原厂最前级和 SOS/TOS 没有改动。首次通过核心 Debian 的 SSH 后，按 desktop 仓库 README 构建 Niri/Noctalia，安装服务和横屏配置。APP 空闲空间不足时不要直接往 APP 塞编译缓存；在 UDA 已有文件系统和备份的前提下，用你自己的 PARTUUID 把它挂到 `/srv/mocha-data`，再把 `/usr/local` 下的大型桌面文件目录 bind mount 过去。这只迁走自编译产物，APT 的 `/usr/lib` 和 `/usr/share` 仍占 APP，装 Firefox 和全部运行库之前要先预估空间。原机用过数据分区上的独立桌面环境，本次规范化的 rootfs 脚本只覆盖核心 APP 安装路线，完整桌面 rootfs 迁移和分区扩容还没有重新验收过的自动教程；把编译缓存挪走不等于解决系统分区容量问题。

默认配置横屏，最小充电界面竖屏并直接画到 framebuffer；装好充电政策与界面后先跑一次限时、可回退的测试，确认按住电源 2 秒能直接进桌面，再启用 `/boot/mocha-charger.enabled`。Wi-Fi 用 `nmcli device wifi connect 'YOUR_SSID' --ask`，密码不写进脚本，固件从合法持有的设备或官方包私有提取后放进对应的 `/lib/firmware`。最后保存四个仓库的 commit、产物 SHA256、`uname`、设备树哈希、冷启动方式、四核是否上线、面板上的真实观察和 journal；历史日志出现时间顺序冲突时，以状态表和后期可复核证据为准。

## 当前状态（2026-10-07）

| 子系统 | 实机状态 | 限制 |
|---|---|---|
| Debian armhf / eMMC | 已持久安装、systemd PID 1 | 仅一台 A0101 验证；GPT 没有重分区 |
| 四核 | CPU 0–3 上线、逐核负载及冷启动通过 | 使用原厂 TLK SMC；CPU DVFS 尚未启用 |
| 默认显示 | 冷启动、横屏、触控、亮度通过 | simpledrm 输出仍有同步/CPU 拷贝开销 |
| 原生 Tegra 双 DSI 与左右链路 | GPU 线性 DMA-BUF 色块实机可见，约 29.8 FPS；native6 的起点 `[0,768]` 在桌面 modeset 后仍正确 | Niri 原生桌面 SIGSEGV；尚未替换默认路径；仅寄存器读数通过，控制台位置/换行仍异常，桌面稳定性未完成 |
| GPU 与 CUDA | Nouveau NVEA / GK20A 硬件着色器通过；Gdev 实验 Driver API 的有限计算通过 | 固件需要自行提取；DVFS/热管理未完成；libcudart 6.5 error 35，完整 CUDA Runtime 未完成 |
| Wi-Fi | BCM4354 扫描、连接、自动连接通过 | 需要板级 NVRAM 和本机 MAC |
| 触控 | 本机 Atmel maXTouch 1664T 点击、滑动、横屏坐标准确 | Mocha 有不同面板/触控批次，不要盲刷 Synaptics 固件 |
| 充电 | 竖屏动画、按键进桌面、BC1.2 DCP 2 A 输入策略通过 | 最小 Linux 充电模式，并非 SoC 完全断电；电量计偶有跳变 |
| 扬声器/麦克风 | 未完成 | RT5671 0x1c NACK，ALSA 无卡；TFA9890 两颗 revision 可读 |
| 蓝牙、摄像头 / OTG / 休眠 | 旧内核 HCI 初始化通过；现代内核完整功能未验证；摄像头、OTG 与休眠未完成 | UART/固件/GPIO 及配对、音频待完成；控制器、传感器、VBUS 与恢复链路待适配 |
| 视频播放与壁纸预览 | FFmpeg H.264 72 帧解码、Firefox HTML5 播放通过；缩略图与专用壁纸目录修复通过 | 软件解码可用，Tegra124 硬件编解码未完成；壁纸需正确安装 Noctalia 数据文件 |

最近一轮暂停时，平板上跑的是临时 native6-order 内核。此次整理只发布源码和文档，不继续实机调试，也不把实验配置改成默认。

## 未实现与计划

| 条目 | 说明 | 出处 |
|---|---|---|
| RT5671 音频 | 0x1c 在官方 1.2 V ldoen、PMIC 32k 门控、GPIO5 mux、12.288 MHz MCLK 下仍 NACK；分离 I2C 读写与 100 kHz 速率测试仍 NACK；TFA9890 两颗 revision 0080 可读，MTP0000 不证明校准缺失，因为完整 DSP 时序未运行；官方 TFA 驱动与 machine（I2S0→AIF1，AIF2→左右 TFA，48k/16bit/stereo）已编译但声卡不可用，没有写 MTP 或绕过扬声器保护；旧 MIUI 内核的 RAM 实验白屏且无 USB，保留日志也没有得到成功的音频参考，用户反馈官方 MIUI 曾正常发声 | docs/STATUS.md、docs/ISSUES.md、docs/INSTALL.md |
| 原生显示路径：双 DSI 最终画面与 Niri native 崩溃 | 寄存器读数正确，但用户仍报告日志从屏幕中间开始、右侧内容绕回左边和位置错误，画面坐标、stride、格式与控制台都未验证完。block-linear framebuffer 的 atomic TEST_ONLY 返回 EINVAL，随后 fallback 启动，Mesa/Gallium 内部跳到 PC=0，实测用 GDB 捕获 LR 并匹配库 Build ID。Mesa 25.0.7-2+deb13u1（Build ID `fd7dcad10de8c89211ebe69ae8c8dda302f047d0`）返回偏移 0xd645bc，匹配 Debian 调试符号 `tegra_fence_server_sync`、`src/gallium/drivers/tegra/tegra_context.c:834`，空函数指针来源待确认，不能把定位称为修复；`CONFIG_COREDUMP=y` 但 `CONFIG_ELF_CORE` 关闭，第一次 core 捕获没有生成文件，改用 ARM gdbserver 抓栈；缺失的驱动回调与缓冲协作待修，DMA-BUF、CPU_PREP 和 copy 未测完，不能标注 zero-copy 完成 | docs/STATUS.md、docs/ISSUES.md |
| Tegra124 硬件编解码与完整 CUDA Runtime | VDE 非标准 tile 布局没有完整格式；libcudart 6.5 error 35（驱动版本不足），真实 NVIDIA 库依赖旧驱动 ABI | docs/STATUS.md、docs/ISSUES.md、SOURCES.md |
| 蓝牙、摄像头 / OTG / 休眠 | 现代内核的 UART/固件/GPIO、配对与音频待完成；控制器、传感器、VBUS 与恢复链路待适配 | docs/STATUS.md |
| 调频、热管理与挂起 | 四核上线不代表 CPU DVFS、热管理或 suspend 可用；CPU/GPU 调频与超频保持未启用，当前先处理原生显示和音频发现 | docs/STATUS.md、docs/ISSUES.md、CONTRIBUTING.md |
| 完整桌面 rootfs 迁移、分区扩容与 32 GB / 其他 GPT | 新规范化脚本只覆盖核心 APP 路线，扩展方案没有重新验收过的自动教程，GPT 未重分区；其他容量需要先自行调整安装计划、initramfs 布局检查与引导根分区 | docs/INSTALL.md |
| 充电电量计与关机充电 | 电量计偶有跳变；最小 Linux 充电模式不是 SoC 完全断电；完全关机充电状态机仍有改进空间 | docs/STATUS.md、docs/ISSUES.md |
| 大文件与 U-Boot 尾块传输 | 限速与固定块减少了卡住，根因没有彻底确认 | docs/ISSUES.md |
| 正式发布就绪度与上游依赖 | 没有提供声称「所有功能可用」的通用镜像；`new_brand_end_to_end_tested=false`，改名后没有重新刷机验收，静态与交叉编译验证不等于可一键刷入；GK20A 微码、BCM4354 无线固件、TFA DSP 参数需自行合法提取，上游下载仍需网络，产物哈希由开发者自己计算 | docs/INSTALL.md、docs/RELEASES.md、docs/VALIDATION.md、LICENSE-NOTES.md、manifests/repos.lock.json |

## 已解决的问题

| 问题 | 处理结果 |
|---|---|
| 一核 → 四核 | 默认主线安全复位接口与原厂 TLK 不匹配，CPU reset vector 被安全世界锁定；参考官方 `reset/platsmp/tegra_sm_interface`，对 `nvidia,mocha` 且显式 opt-in 的设备调用 SMC `0x82000001` 设置分发器，再走 Tegra PMC/flow-controller 的 SMP 操作，四核冷启动与负载通过 |
| 冷启动半屏变色与原生双 DSI 左右反转 | 前者在 Linux 起来之前就左右颜色不同，排除了 compositor 单方面原因，在 U-Boot 面板复位前停止继承的视频/ganged/电源状态并成对发送初始化命令后两轮冷启动通过。后者把 ganged video 路径按官方公式分拆：1536×2048 下每链路 active=2304 字节，HBP70/HFP196/SOL334；DCS short write 返回 4 字节线头，不是 payload 长度，MIPI calibration mask 按 Tegra124 DSIA/B 与 CILC/D 取 0x60/0x0c；`54300000` 链路必须 start0，`54400000` 必须 start768，live 改寄存器会被 modeset 覆盖，native6 设备树把 543 作为 primary、544 作为 secondary。LP 命令阶段频率从 68 MHz 改为已验证 U-Boot 命令阶段的 12 MHz 后，用户看到 4 个 GPU 色块，约 29.8 FPS。同一路径上的桌面左侧四分之一黑条：物理 framebuffer 1536×2048，Niri 横屏后 damage 坐标没有完整转换，最后 512 行未提交，临时用 legacy KMS 绕开 damage 属性可以消除黑条，Smithay 补齐旋转 damage 后实际画面通过，这里要区分「显示正确」与「没有 CPU 拷贝」 |
| PMIC 初始化后屏幕逐渐熄灭 | 用早期色条、early framebuffer 和 initcall 暂停把范围缩到 I2C/PMIC；恢复 GPIO 后显示稳定，去掉 CPU/core/PLL 外部控制声明后 Palmas 供电注册正常。故障无法归因到某一路寄存器的单独写入，也不声称所有继承电压完全不变 |
| USB gadget 未连接 | device 角色与 PHY 的 `dr_mode` 必须一致；重复写已绑定 gadget 会让 SSH 失败，改成复用 gadget、恢复地址与接口，并把 Wi-Fi SSH 对 USB 服务的 `Requires` 改为 `Wants`；`reboot-argument=bootloader` 实测进 APX（0955:7015），不能宣称它能返回原厂 Fastboot |
| 充电界面与按键 | ELF interpreter 曾被 copyfile 写成 0644，内核执行返回 126，修正为 0755 并检查最终 CPIO 元数据；充电 target 隔离桌面后 logind 仍处理电源键，改用 `systemd-inhibit` 接管 `handle-power-key`，由界面返回 10 进桌面、20 关机。BC1.2 识别 DCP 后走 2 A 输入策略，PC 未知 500 mA，CDP 1.5 A，电池侧仍是 960 mA/4.208 V，2 A 输入不是 2 A 电池实测，实测约 +0.85 A 桌面 / +1 A 最小模式，温度正常 |
| 视频、壁纸与 CUDA | 补上 FFmpeg/libavcodec/MPV 后软件视频和 Firefox HTML5 播放通过；Noctalia 壁纸列表改用专用目录并安装数据文件后缩略图通过；Gdev 修好代码上传、GPU 引用和 ARM 缓存后 257 与 8193 的整数计算通过 |

## 恢复与回退

原厂 bootloader、TOS、SOS、GPT 没有被本方案改写；默认 LNX 只是原厂加载的 Android 容器，payload 是 U-Boot。

1. 长按电源约 15 秒后松开，按电源＋音量减进入原厂 Fastboot。
2. `fastboot devices` 确认设备，然后 `fastboot boot YOUR_VERIFIED_UBOOT.img` 临时加载。
3. 要读写分区，进入只读 RAM Linux，检查自己的 `layout.env`；恢复 APP/LNX 用先前的私有备份并回读。保留自己的完整分区表、APP 与 LNX 备份及匹配哈希；16 GB 设备上的 APP/LNX 偏移不是所有 SKU 的通用恢复地址，本次公开也没有上传设备备份、解锁数据或原厂私钥。
4. 不要通过 U-Boot 的 flash 命令恢复：公开构建禁用了写操作，RAM Linux 脚本只支持 APP/LNX，并拒绝已挂载的存储。
5. `reboot bootloader` 在本机实际进入 NVIDIA APX（0955:7015），不能作为可靠的 Fastboot 入口；APX 也不等于设备永久损坏。
6. native 临时实验出黑屏时不要直接改默认 DT，用默认 uImage、stable DT 和非实验桌面恢复。
7. 充电 target 循环进入时，临时 bootargs 加 `systemd.unit=multi-user.target`，核心系统启动后删除 `/boot/mocha-charger.enabled`。

## 产物命名与版本规则

- 人类名称 mocha moze linux 6.12.111-moze.1；`UTS_RELEASE` 与模块目录 `6.12.111-moze.1`；Makefile `NAME` 为 `mocha moze linux`，`CONFIG_LOCALVERSION` 为 `-moze.1`，关闭 `LOCALVERSION_AUTO`。内核构建目录产出 `uImage`、`Image`、`mocha.dtb`、`modules/`、`.config`、`SHA256SUMS`，复制进 rootfs 时改名为 `/boot/uImage-desktop` 和 `/boot/mocha-desktop.dtb`；drivers 产出针对该 release 的 `.ko`，desktop 产出本机 ARMhf ELF、配置/服务与充电界面，boot 产出 `.img` 和 `.config`，debian 产出除私有密钥之外的 rootfs ext4 与 manifest。
- 每次发布生成 `SHA256SUMS`；多仓库 release 应固定内核、boot、drivers、desktop 四个 commit 及所有构建产物 SHA256。新构建不能冒用旧镜像的 SHA256，旧镜像哈希不能沿用；公开 DTS 已去除本机身份、旧 bootargs 和 initrd 地址，其 SHA256 自然与历史 DT 不同。

历史通过的私有镜像（仅用于对照，不随仓库分发）：

| 产物 | SHA256 | 意义 |
|---|---|---|
| 旧 uImage-desktop | 1b76bfbef11ae473d227f47b68650f9bf09dc5d94b2676e2c56b9bbe5d6b43a9 | 默认四核桌面内核，旧 release 名称 |
| 默认背光 DT | 7b217aa0c8151615d5852152879de7a90a7971aca78ad115e30948d9cf1eccf7 | 已验证触控、GPU、背光 |
| 默认 LNX 前缀 | 8760cbdbc123e4350287874b9b75e6edd3d74ab78be3262b6ec2fd1175a8f7d5 | 569344 字节，普通开机桌面已验证 |
| native4 uImage | 682da8b2f9a5e3a241850fd019ce5a40467f5e42e5f6e7817868a356879c7e17 | 原生 DSI 实验内核 |
| native6 DT | f92ee8c250fd7b06f1bec03a935182c7e92dc35232d74901199e4a3a51a9a7b3 | 链路起点纠正；桌面仍崩溃 |

## 验证范围

2026-10-08 的发布验证针对源码和安装资料；按用户要求暂停实机开发，本次没有重启、刷写或改动平板。

| 检查 | 结果 | 实际范围 |
|---|---|---|
| Linux 完整源树 | 86,744 个 Git 跟踪文件 | Debian 原始基线、Mocha 变更与规范化构建提交分离 |
| 两种设备树与 stable 内核配置 | stable-desktop/native-experimental 均由 dtc 生成 DTB，警告保留；olddefconfig 通过，kernelrelease=6.12.111-moze.1 | 编译成功不代表外设运行完成；没有重新构建并刷机验收整个新命名内核 |
| 充电 UI、DMA-BUF 色块、CUDA probe | ARM 交叉编译通过 | 原机此前竖屏充电/按键、色块可见与有限 CUDA 计算已实测，不代表完整桌面或 runtime，新统一安装路径未重刷 |
| Android U-Boot 封装器 | 用实际 U-Boot ELF/payload 检查头部、长度、载入字段和 SHA1 | 新容器名称导致哈希变化，没有新刷机验收 |
| 脚本、配置与多仓库来源 | 逐个 shell 语法、Python AST、TOML/JSON 解析通过；上游 tag/revision、Linux 源压缩包 SHA256、四仓库 commit 锁 | 构建依赖配置核对实际 Linux VM 资料，规范化安装未端到端跑完；上游下载仍需网络，产物哈希需开发者自己计算 |
| 公开内容筛选与 GitHub 上传 | 排除凭据、设备备份、校准、专有固件和编译镜像；五个 public 仓库，远端 main 与本地提交逐一对照 | 上游 Linux 测试样例仍保持原始源码，不能按字符串判定为私人凭据；`repos.lock.json` 锁定其余四仓库的配套版本 |

只有一台 A0101 实机验证过。静态检查和交叉编译通过不等于新版本可以一键刷入；安装要按 RAM、APP、LNX 逐级验证。

## 文档索引

- [手把手安装](docs/INSTALL.md)：主机工具、自己生成密钥、构建、临时启动、备份、写入与验证。
- [设计与跨仓库关系](docs/ARCHITECTURE.md)、[问题与排查记录](docs/ISSUES.md)、[本地文件如何整理](docs/FILE-ORGANIZATION.md)。
- [恢复与回退](docs/RECOVERY.md)、[硬件差异](docs/HARDWARE.md)、[源码来源](SOURCES.md)、[发布验证范围](docs/VALIDATION.md)、[产物与版本规则](docs/RELEASES.md)。

## 协作方式

提交时注明仓库 commit、内核 release、DT SHA256、是冷启动还是 Fastboot 临时启动、实际屏幕观察和系统日志。编译通过不能标成实机通过，DRM page flip 成功不能标成面板有图，有限 CUDA Driver API 自检不能标成完整 Runtime。先用临时镜像验证，再讨论默认引导。不要提交设备密钥、Wi-Fi 密码、完整存储镜像、MAC 地址或未经许可的固件。当前先处理原生显示和音频发现，CPU/GPU 调频与超频保持未启用。

## 许可证与来源

本仓库新增的内核与驱动适配、工具和文档采用 GPL-2.0-only，条款见 [LICENSE](LICENSE)，来源与例外的说明见 [LICENSE-NOTES.md](LICENSE-NOTES.md)。Linux、U-Boot 和厂商 GPL 文件保留各自的 SPDX、版权头和原许可证；Niri/Smithay、Noctalia、Gdev 等外部项目沿用上游许可，本项目补丁不改变上游许可证。本仓库不授予 NVIDIA CUDA、MIUI 固件、Wi-Fi/蓝牙固件或 TFA DSP 参数的再分发权，需自行从合法持有的设备或官方包中提取。

| 项目 | 基线/出处 | 使用方式 |
|---|---|---|
| Linux | Debian linux-source-6.12，Makefile 6.12.111，源压缩包 SHA256 `dcb52c568b7f906ec831feeadabb1d60435040bf0f1f3976be371c9a5c12582a` | 完整源码快照，保留 COPYING/LICENSES；Mocha 源码修改单独提交 |
| U-Boot | [u-boot](https://source.denx.de/u-boot/u-boot)，v2026.07 | clone 固定 tag，覆盖仓库 overlay 后构建 |
| 厂商源码 | [Xiaomi_Kernel_OpenSource](https://github.com/MiCode/Xiaomi_Kernel_OpenSource)，mocha-kk-oss，`79b4898e25fe3b506ff902e182b47068598c838a` | TLK/SMP、面板、PMIC、USB、音频、触控依据 |
| 社区 Mocha | [Insei/linux](https://github.com/Insei/linux)，`1e3857d7a1ea87cd2cc15eca2d36f57cb591c4bf` | 早期板级/面板参考，后续逐项对照官方与实机 |
| Niri | [niri-wm/niri](https://github.com/niri-wm/niri)，v26.04 | ARMv7 构建，Smithay `ff5fa7df392cecfba049ffed55cdaa4e98a8e7ef` 旋转损伤补丁 |
| Noctalia | [noctalia-dev/noctalia](https://github.com/noctalia-dev/noctalia)，v5.2.1 | 此版本为 C++/Meson 项目，不混用旧 QML shell 的安装方式 |
| Mesa 与 CUDA/Gdev | Debian 25.0.7-2+deb13u1；原厂 CUDA 6.5 包和实验 Gdev 兼容层 | Mesa 是默认渲染与 native 崩溃证据，不发布 NVIDIA 用户态库；CUDA 只做示例/接口检查，完整运行时未通过 |

官方 MIUI V9.2.4.0 固件包与原设备固件只用于对照和私有提取，不随仓库分发。构建版本与固定 SHA256 另见 `manifests/source-provenance.json`，其中也列出了不进入公开仓库的材料（设备备份、凭据、私钥、专有固件、CUDA deb、编译镜像、虚拟机磁盘）；外部 GPL 源码的版权头必须保留。
