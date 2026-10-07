# 在 Mocha 上安装 Debian：开发者逐步路线

## 0. 阅读范围

适用于 Xiaomi Mi Pad 1 / Mocha / A0101 / Tegra K1 ARMv7。不是 Mi Pad 2/3/4，也不是 ARM64。
这是源码开发快照。原项目已在一台设备持久运行，但本次规范化脚本和 `6.12.111-moze.1` 新名称尚未进行新的完整刷机验收。没有提供声称“所有功能可用”的通用成品镜像。
先选择稳定 simpledrm 桌面；native 实验只供开发。不能把色块显示成功当成 Niri 原生显示完成。

实际验证的 16 GB 原厂布局：APP=`mmcblk0p26`，起始524288、2612431个512字节扇区；LNX=`p22`，起始393216、40960扇区；UDA=`p29`。APP只有1337564672字节。
32 GB版本或不同GPT必须先调整安装计划、initramfs中的布局检查及引导根分区。不要复制本机PARTUUID、MAC、密钥或校准数据。

## 1. Linux 构建主机

建议 Debian13 amd64 VM/实体机，至少20GB空闲空间；Windows只用于原厂Fastboot和SSH，完整Linux源码应在大小写敏感文件系统构建。

```sh
sudo apt update
sudo apt install git python3 build-essential bc bison flex libssl-dev libelf-dev \
  gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf binutils-arm-linux-gnueabihf \
  device-tree-compiler u-boot-tools debootstrap qemu-user-static binfmt-support \
  dropbear-bin e2fsprogs dosfstools cpio gzip xz-utils rsync curl openssh-client adb fastboot \
  pkg-config meson ninja-build clang libclang-dev cmake
git clone https://github.com/Pisces-Moze/mocha-moze-debian.git
cd mocha-moze-debian
python3 tools/workspace.py fetch --dest ../mocha-workspace
cd ../mocha-workspace
mkdir -p artifacts
ssh-keygen -t ed25519 -f artifacts/developer-key
```

需要sudo的构建步骤只针对Linux构建主机的临时rootfs/挂载，不在正在运行的平板系统上执行。

私钥只放本地。`developer-key.pub` 是RAM SSH授权输入；每次生成RAM镜像都会创建新的Dropbear host key，构建输出会列出指纹。连接时记录自己的known_hosts。

## 2. 构建内核、设备树、外置驱动

```sh
cd mocha-moze-linux
bash moze/tools/build.sh stable ../artifacts/kernel
cd ../mocha-moze-drivers
bash tools/build-backlight.sh ../mocha-moze-linux ../artifacts/kernel
cd ..
```

输出包括 `uImage`、`Image`、`mocha.dtb`、`modules/` 和 `SHA256SUMS`。release为`6.12.111-moze.1`，外置模块必须用这一构建目录的头文件和Module.symvers。
稳定设备树来自最终实测配置，已去除设备私有身份及旧initramfs地址。需要自己提取固件，见drivers的firmware/README.md；无线NVRAM不能使用别人的MAC。
音频模块不在默认安装中启用，因为还没有完整声卡。

## 3. 构建 APP 核心系统和两个 initramfs

```sh
sudo bash mocha-moze-debian/tools/build-rootfs.sh \
  artifacts/rootfs artifacts/developer-key.pub artifacts/kernel
sudo bash mocha-moze-debian/tools/build-initramfs.sh \
  artifacts/rootfs artifacts/developer-key.pub artifacts/ram-install.cpio.gz install
sudo bash mocha-moze-debian/tools/build-initramfs.sh \
  artifacts/rootfs artifacts/developer-key.pub artifacts/initramfs.cpio.gz emmc
sudo cp artifacts/initramfs.cpio.gz artifacts/rootfs/boot/initramfs.cpio.gz
# 外置背光模块要放入新内核自己的模块目录，不使用原机旧release的.ko。
sudo install -d artifacts/rootfs/usr/lib/modules/6.12.111-moze.1/extra
sudo install -m644 mocha-moze-drivers/backlight/mocha_miui_backlight.ko \
  artifacts/rootfs/usr/lib/modules/6.12.111-moze.1/extra/
sudo depmod -b artifacts/rootfs 6.12.111-moze.1
sudo bash mocha-moze-debian/tools/make-app-image.sh \
  artifacts/rootfs artifacts/debian-app.img 1337564672
```

核心rootfs使用Debian13/trixie armhf。APP保持小型系统；大型桌面构建与数据可移到自己备份、检查后的UDA，或在完成GPT研究后另行扩容。本项目没有替你重分区。
在生成APP镜像前，把自己提取的必要固件放入`artifacts/rootfs/usr/lib/firmware/`，特别是GK20A微码和BCM4354无线文件；未提供无线固件时仍可先使用USB SSH。

镜像ext4关闭64bit、metadata_csum和orphan_file，保持已测试U-Boot的只读加载兼容性。

## 4. 构建只读 U-Boot

```sh
bash mocha-moze-boot/tools/build.sh artifacts/uboot
python3 mocha-moze-boot/tools/pack-android.py \
  artifacts/uboot/u-boot-dtb.bin artifacts/uboot/u-boot \
  artifacts/mocha-uboot.img
```

U-Boot text base=0x80a00000；Android legacy header保留Mocha已验证加载字段。完整说明见boot仓库。
该U-Boot编译时禁止MMC写、Fastboot flash、saveenv和GPT编辑。首次安装仍通过RAM Linux写APP/LNX。

## 5. 只在 RAM 临时运行

平板电量充足后按电源＋音量减进入原厂Fastboot。主机检查：

```sh
fastboot devices
fastboot -s YOUR_SERIAL boot artifacts/mocha-uboot.img
```

如果APP还没有Debian，引导失败后U-Boot进入USB Fastboot。先核对该U-Boot的`getvar all`/产品识别，然后用RAM加载工具：

```sh
python3 mocha-moze-boot/tools/load-ram.py --serial YOUR_UBOOT_SERIAL \
  --kernel artifacts/kernel/uImage --dtb artifacts/kernel/mocha.dtb \
  --initrd artifacts/ram-install.cpio.gz
```

加载器将数据分成1MiB固定大小传输块、末块补零、RAM拷贝后启动，不执行flash。旧的非固定尾块曾卡住；遇到超时回原厂Fastboot重试，不能继续用不完整的RAM数据。
内核通过USB RNDIS提供172.31.124.2/30，主机172.31.124.1。Windows可能需要“USB RNDIS”驱动；Linux可手工给对应USB网卡配地址。DHCP不提供默认路由。

```sh
ssh -i artifacts/developer-key root@172.31.124.2
cat /proc/1/comm                  # 应为init，不是已安装系统的systemd
cat /sys/class/block/mmcblk0/ro   # 应为1
cat /proc/mounts                 # eMMC无挂载
```

## 6. 自己备份并保存分区计划

在RAM Linux里核对 `lsblk -o NAME,SIZE,PARTLABEL,PARTUUID,MOUNTPOINTS`（BusyBox环境可以读sysfs或装工具）。
工具保存自己的eMMC CID和APP/LNX起点/长度，不使用维护者设备的布局哈希。为让现有小RAM仍可用，本仓库提供的 `storage.sh` 使用BusyBox即可运行：

```sh
scp -O -i artifacts/developer-key mocha-moze-debian/tools/storage.sh root@172.31.124.2:/tmp/
ssh -i artifacts/developer-key root@172.31.124.2 'sh /tmp/storage.sh plan > /tmp/layout.env'
scp -O -i artifacts/developer-key root@172.31.124.2:/tmp/layout.env artifacts/
ssh -i artifacts/developer-key root@172.31.124.2 \
  'dd if=/dev/mmcblk0 bs=512 count=2048' > artifacts/gpt-prefix.bin
ssh -i artifacts/developer-key root@172.31.124.2 \
  'dd if=/dev/mmcblk0p22 bs=1048576' > artifacts/LNX-before.img
ssh -i artifacts/developer-key root@172.31.124.2 \
  'dd if=/dev/mmcblk0p26 bs=1048576' > artifacts/APP-before.img
sha256sum artifacts/*before.img artifacts/gpt-prefix.bin > artifacts/backup.sha256
```

备份GPT末尾和UDA中的个人数据也应自己完成；上述prefix不是完整GPT灾难恢复副本。原始镜像和layout.env只属于你，不提交Git。

## 7. 写 APP，回读，再从内置存储临时启动

确认layout.env是刚刚从自己的设备读出的，APP/LNX与本指南16GB布局一致。先把镜像传入RAM的/tmp并比较哈希；空间不足时不能截断上传。RAM安装的/tmp在initramfs根目录，不另挂默认半内存大小的tmpfs；APP文件约1.25GiB，上传前确认没有桌面运行、RAM仍足够。

```sh
scp -O -i artifacts/developer-key artifacts/debian-app.img artifacts/layout.env root@172.31.124.2:/tmp/
sha256sum artifacts/debian-app.img
ssh -i artifacts/developer-key root@172.31.124.2 \
  'sha256sum /tmp/debian-app.img'
ssh -i artifacts/developer-key root@172.31.124.2 \
  'sh /tmp/storage.sh write APP /tmp/debian-app.img /tmp/layout.env REPLACE_APP'
```

这个步骤删除APP中的旧系统内容。脚本先检查RAM PID1、设备CID、起点、长度、无挂载，再临时解锁块设备、写入、回读SHA256、重新只读。不改GPT、TOS、SOS、UDA。
返回原厂Fastboot，重新执行 `fastboot boot artifacts/mocha-uboot.img`。这次U-Boot应读APP自己的/boot三个文件，无需传RAM内核。
通过USB SSH检查：

```sh
cat /proc/1/comm
uname -r
cat /sys/devices/system/cpu/online
findmnt /
systemctl --failed
```

应为systemd、6.12.111-moze.1、0–3、根分区APP。必须实际看到双侧正常画面，而非只看日志返回成功。

## 8. 最后写 LNX

从APP临时启动验证后，再回到只读RAM安装环境（重新Fastboot临时启动并加载ram-install）。

```sh
scp -O -i artifacts/developer-key artifacts/mocha-uboot.img artifacts/layout.env root@172.31.124.2:/tmp/
ssh -i artifacts/developer-key root@172.31.124.2 \
  'sh /tmp/storage.sh write LNX /tmp/mocha-uboot.img /tmp/layout.env REPLACE_LNX'
```

只写LNX镜像长度并验证前缀，不清空整个分区。普通关机后电源键开机，至少重复两次冷启动并检查四核、USB、左右屏幕。
无法自动进入时，用原厂Fastboot加载已验证临时U-Boot；原厂最前级和SOS/TOS没有改动。

## 9. 桌面和充电

首次通过核心DebianSSH后按desktop仓库README构建Niri/Noctalia，安装服务和横屏配置。APP空闲不足时，不直接往APP塞入编译缓存。
在自己的UDA已有文件系统和备份前提下挂载到/srv/mocha-data（用自己的PARTUUID），将/usr/local的大型桌面文件目录bind mount到该数据目录。
这只迁走自编译产物，APT的/usr/lib和/usr/share仍占APP；安装Firefox和全部运行库前必须预估所需空间。原机采用过数据分区上的独立桌面环境，本次新规范化rootfs脚本只完成核心APP安装路线；完整桌面rootfs迁移/分区扩容尚无重新验收的自动教程，见desktop README。不要把单纯迁走编译缓存视为解决系统分区容量问题。
默认配置横屏；最小充电UI竖屏。安装充电政策与UI后先运行一次限时/可回退测试，确认按住电源2秒可直接进桌面，再启用/boot/mocha-charger.enabled。

Wi-Fi用 `nmcli device wifi connect 'YOUR_SSID' --ask`，密码不写进脚本。固件合法私有提取后放对应/lib/firmware。

## 10. 记录你的结果

保存四仓库commit、产物SHA256、uname、设备树哈希、冷启动方式、四核上线、面板真实观察和journal。
当前仍需开发：RT5671音频、Niri native fence崩溃、硬件编解码、完整CUDA运行时、蓝牙/摄像头/OTG/休眠。详见ISSUES.md。
