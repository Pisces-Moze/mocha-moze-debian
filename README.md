# Mocha Moze Debian

Xiaomi Mi Pad 1 / A0101 / Mocha / Tegra124 的 Debian armhf 多仓库适配工程。
内核名称：**mocha moze linux 6.12.111-moze.1**。Linux release 使用 `6.12.111-moze.1`，保留可用于模块目录的合法格式。

这是 2026-10-07 的开发快照，不是所有外设完成的安装发行版。默认可用桌面和原生显示实验明确分开。
完整安装路线见 [INSTALL.md](docs/INSTALL.md)，首次阅读请同时查看 [状态表](docs/STATUS.md) 和 [回退](docs/RECOVERY.md)。

## 五仓库结构

| 仓库 | 负责内容 |
|---|---|
| [mocha-moze-debian](https://github.com/Pisces-Moze/mocha-moze-debian) | 总入口、版本锁、rootfs、RAM 引导安装、分区核对和文档 |
| [mocha-moze-boot](https://github.com/Pisces-Moze/mocha-moze-boot) | U-Boot 2026.07 覆盖源码、Android 容器、双 DSI 冷启动交接 |
| [mocha-moze-linux](https://github.com/Pisces-Moze/mocha-moze-linux) | Debian Linux 6.12.111 完整源码基线及 Mocha 修改、配置和 DTS |
| [mocha-moze-drivers](https://github.com/Pisces-Moze/mocha-moze-drivers) | MIUI 背光/音频移植、固件提取说明、GPU/CUDA诊断和驱动实验 |
| [mocha-moze-desktop](https://github.com/Pisces-Moze/mocha-moze-desktop) | Niri/Smithay 补丁、Noctalia 配置、服务、竖屏充电界面 |

```
mocha-workspace/
  mocha-moze-debian/       # docs/ tools/ manifests/
  mocha-moze-boot/         # overlay/ configs/ tools/
  mocha-moze-linux/        # Linux 原目录 + moze/configs,dts,tools
  mocha-moze-drivers/      # backlight/ audio/ diagnostics/ firmware/
  mocha-moze-desktop/      # config/ patches/ charging/ tools/
  artifacts/              # 自己构建的产物，不提交 Git
```

## 联动入口

```sh
git clone https://github.com/Pisces-Moze/mocha-moze-debian.git
cd mocha-moze-debian
python3 tools/workspace.py fetch --dest ../mocha-workspace
```

`manifests/repos.lock.json` 固定其余四仓库 commit。构建顺序为 kernel → 外置驱动 → U-Boot/容器 → rootfs/桌面 → RAM 验证 → APP → LNX。
不要混用不同内核 release 的 `.ko`，也不要把 native 实验 DT 当成稳定桌面配置。

## 当前状态

| 子系统 | 实机状态 | 限制 |
|---|---|---|
| Debian armhf / eMMC | 已持久安装、systemd PID 1 | 仅一台 A0101 验证；GPT 没有重分区 |
| 四核 | CPU 0–3 上线、逐核负载及冷启动通过 | 使用原厂 TLK SMC；CPU DVFS 尚未启用 |
| 默认显示 | 冷启动、横屏、触控、亮度通过 | simpledrm 输出仍有同步/CPU 拷贝开销 |
| 原生 Tegra 双 DSI | GPU 线性 DMA-BUF 色块实机可见，约 29.8 FPS | Niri 原生桌面 SIGSEGV；尚未替换默认路径 |
| 左右链路 | native6 的起点 `[0,768]` 在桌面 modeset 后仍正确 | 仅寄存器读数通过；控制台位置/换行仍异常，桌面稳定性未完成 |
| GPU | Nouveau NVEA / GK20A 硬件着色器通过 | 固件需要自行提取；DVFS/热管理未完成 |
| Wi-Fi | BCM4354 扫描、连接、自动连接通过 | 需要板级 NVRAM 和本机 MAC |
| 触控 | 本机 Atmel maXTouch 1664T 点击、滑动、横屏坐标准确 | Mocha 有不同面板/触控批次，不要盲刷 Synaptics 固件 |
| 充电 | 竖屏动画、按键进桌面、BC1.2 DCP 2 A 输入策略通过 | 最小 Linux 充电模式，并非 SoC 完全断电；电量计偶有跳变 |
| 扬声器/麦克风 | 未完成 | RT5671 0x1c NACK，ALSA 无卡；TFA9890 两颗 revision 可读 |
| 蓝牙 | 旧内核 HCI 初始化通过；现代内核完整功能未验证 | UART/固件/GPIO及配对、音频待完成 |
| 视频播放 | FFmpeg H.264 72 帧解码、Firefox HTML5 播放通过 | 软件解码可用；Tegra124 硬件编解码未完成 |
| 壁纸预览 | 缩略图与专用壁纸目录修复通过 | 需正确安装 Noctalia 数据文件 |
| CUDA | Gdev 实验 Driver API 的有限计算通过 | libcudart 6.5 error 35；完整 CUDA Runtime 未完成 |
| 摄像头 / OTG / 休眠 | 未完成 | 控制器、传感器、VBUS 与恢复链路待适配 |


## 文档索引

- [手把手安装](docs/INSTALL.md)：主机工具、自己生成密钥、构建、临时启动、备份、写入与验证。
- [设计与跨仓库关系](docs/ARCHITECTURE.md)、[问题/排查记录](docs/ISSUES.md)。
- [恢复与回退](docs/RECOVERY.md)、[硬件差异](docs/HARDWARE.md)、[源码来源](SOURCES.md)。
- [产物、命名和版本规则](docs/RELEASES.md)：重新命名的源码尚未完成新版本全流程实机验证，旧镜像哈希不能沿用。

- [发布验证范围](docs/VALIDATION.md)、[本地文件如何整理](docs/FILE-ORGANIZATION.md)。
