# 回退和恢复

原厂 bootloader、TOS、SOS、GPT没有被本方案改写。默认LNX只是原厂加载的Android容器，其payload为U-Boot。

1. 长按电源约15秒后松开，按电源＋音量减进入原厂Fastboot。
2. `fastboot devices` 确认设备，然后 `fastboot boot YOUR_VERIFIED_UBOOT.img` 临时加载。
3. 要读写分区，进入只读RAM Linux，检查自己的layout.env；恢复APP/LNX使用先前私有备份并回读。
4. 不要通过U-Boot的flash命令恢复：公开构建禁用了写操作。RAM Linux脚本只支持APP/LNX，并拒绝已挂载存储。
5. `reboot bootloader` 在本机实际进入NVIDIA APX(0955:7015)，不能作为Fastboot可靠入口；APX也不等于设备永久损坏。
6. native临时实验出黑屏时，不直接更改默认DT。使用默认uImage、stable DT和非实验桌面恢复。
7. 充电target循环进入时，临时bootargs加`systemd.unit=multi-user.target`；核心系统启动后删除/boot/mocha-charger.enabled。

保留自己的完整分区表、APP和LNX备份及匹配哈希。16GB设备上的APP/LNX偏移不是所有SKU的通用恢复地址。
本次公开没有上传设备备份、解锁数据或原厂私钥。
