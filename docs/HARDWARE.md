# 实机与硬件差异

目标为 Xiaomi Mi Pad 1 A0101 / Mocha，Tegra K1/Tegra124 ARMv7 32 位，GK20A/NVEA GPU，1536×2048 双 DSI 面板。
本机 eMMC 是 16 GB，APP 在 p26、LNX 在 p22、UDA 在 p29；这些编号只属于已记录的分区布局，安装工具必须检查分区名称和容量。

本机触控实际为 Atmel maXTouch 1664T，I2C 0x4a，IRQ GPIO143，reset GPIO84；最初试 Synaptics DSX 无响应，后来与官方 Atmel with_dummy 配置比对差异为零。没有升级控制器固件。
其他批次可能使用不同触控，不要因为“官方源码含 Synaptics”就强制刷写它。

供电 Palmas/TPS65913；充电 BQ24192（Linux 通用 bq24190 驱动）；电量计 BQ27520-G4；背光 LP8556。
音频 RT5671 + 左右 TFA9890，主机时钟 12.288 MHz；两个功放地址 0x34/0x37，codec 0x1c。
BCM4354 为 Wi-Fi/蓝牙组合芯片。板级 NVRAM 和 MAC、BT地址来自自己的原设备，仓库不提供他人的唯一身份。
