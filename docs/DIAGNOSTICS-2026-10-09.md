# 五仓库继续诊断：2026-10-09

日期来自操作端（Asia/Shanghai）；原型机时钟不作为采集日期依据。五仓库没有开放的 GitHub Issue，现有未完成项以 STATUS/ISSUES 及各 README 为准。

## 本次实机读取

原始结果：[只读状态 JSON](diagnostics/2026-10-09-status.json)、[EGL fence 对照](diagnostics/2026-10-09-egl-fence-baseline.txt)。启动方式未确认，记录为 `unknown`；没有把 USB 已连接推断为普通冷启动或临时 Fastboot。

另保存 [Tegra 包装层崩溃重现](diagnostics/2026-10-09-tegra-wrapper-baseline.json) 与 [GDB remote 寄存器](diagnostics/2026-10-09-tegra-wrapper-registers.json)：仅为独立 probe 设置 `MESA_LOADER_DRIVER_OVERRIDE=tegra`，renderer 为 `tegra`，在 `eglWaitSyncKHR` 触发 SIGSEGV。PC/R3 均为零，LR 去掉 Thumb bit 后的相对偏移为 `0xd645bc`，调用指令 `98 47`（Thumb BLX R3）；运行 libgallium Build ID `fd7dcad10de8c89211ebe69ae8c8dda302f047d0` 与历史 Niri 匹配。这是当前运行库的空回调证据，不是候选修复实机通过，也不覆盖 native KMS/面板。

随后在 Debian 13／GCC 14.2.0 构建机上完整交叉构建候选 Mesa，上传到原型机的独立数据目录并核对逐文件 SHA256。[候选库 EGL 回归记录](diagnostics/2026-10-09-mesa-candidate-egl.json) 中，Nouveau/NVEA 与进程级 Tegra 包装层都通过 32 轮 fence 等待和共享像素检查，Tegra 的 `eglWaitSyncKHR` 不再崩溃。实际映射的 EGL Mesa、GBM 和 Gallium 均来自候选目录，stderr 为空；候选 Gallium Build ID 为 `9655e407b21f062859570f90c2acd6e3a5c7b7a0`，SHA256 为 `e89304a3a2f6e782b67e50325636df458012433d387d1eff6e7fcdfdd3c2b484`。`ldd` 依赖均能解析，原 Niri/Noctalia 进程仍运行，没有失败服务。这覆盖包装层 fence 修复，仍未覆盖 native KMS、Niri、物理面板或 zero-copy。

| 项目 | 当前结果 | 结论边界 |
|---|---|---|
| 内核与系统 | `6.12.111-mocha-experimental-fbdiag`，systemd，CPU `0-3` | 仍是旧内核，未验证新命名的完整安装 |
| 设备树 | live FDT SHA256 `e17c0ea679f8b2f8332a1559b4c3077a3b8791d1ba06cd6da69cdcb3f2a745cf` | live FDT 可能含启动期改动，不冒充磁盘 DTB 哈希 |
| 桌面/DRM | simpledrm 1536×2048；Nouveau；Niri/Noctalia 进程运行 | 未观察物理面板，不宣称 native 图像通过 |
| EGL fence | EGL 1.5，NVEA，32 轮 fence 与共享纹理像素检查通过 | 系统 Mesa，对照只覆盖 Nouveau，未覆盖候选 Tegra 包装层 |
| 音频 | `--- no soundcards ---` | 尚无可用声卡；没有重新做 I2C 电源/寄存器实验 |
| 蓝牙 | 无 HCI；`serial@70006200` 为 `disabled` | 此次既没有启用 UART，也没有验证配对/音频 |
| USB 电源 | 输入限流 500000 µA，电池电流约 −0.5 A，约 28 °C | 桌面运行时 PC USB 的 500 mA 输入不足以抵消整机消耗；没有提高 USB 限流 |
| 存储 | APP 约剩 41 MiB，数据分区约剩 1.2 GiB | 构建产物应放独立数据目录，临时诊断脚本放 `/tmp` |
| Core | BINFMT_ELF/COREDUMP 启用，ELF_CORE 关闭 | 运行内核确实不能生成 ELF 用户程序 core |

没有更改默认引导、写 APP/LNX、载入音频实验模块、改 MTP 或调整限流。SSH 私钥的 Windows 文件权限已收紧，以便本机 OpenSSH 正常读取；私钥未复制到仓库或原型机。

## 本次源码完善

| 仓库 | 工作 | 仍需完成 |
|---|---|---|
| desktop | Mesa 25.0.7 可选 fence 回调修复；八组合 C 回归；完整 ARMhf 构建；候选库实机 Nouveau/Tegra fence 与像素回归通过；补齐 GBM 后端路径与构建依赖 | 临时 native 引导，候选库的 Niri/面板验收 |
| linux | stable/native 启用 ELF_CORE；两套配置的 olddefconfig 保留三个 core 前提选项；stable 内核、模块与 DTB 完整构建通过 | native 完整编译、临时引导并实际捕获 core |
| debian | 只读状态采集器、来源与验收记录、配套 commit 锁 | 改名后端到端安装验收仍为 false |
| boot | 核对当前文档中的 RAM 引导和禁写边界，本次无改动 | 新内核临时启动、双侧画面及至少两次普通冷启动仍待验收 |
| drivers | 核对音频/GPU 实验与当前 ALSA/DRM 状态，本次无改动 | RT5671 发现、音频、完整 CUDA、硬件编解码及电源管理仍未完成 |

源码与上述寄存器诊断确认 Mesa Tegra 公开了 Nouveau 未实现的可选 fence 回调；修复候选保留底层可选回调约定，不补造 sync-file 支持。完整说明见 [desktop 的 Mesa fence 文档](https://github.com/Pisces-Moze/mocha-moze-desktop/blob/main/docs/MESA-FENCE.md)。不能把主机回归通过标成 native 桌面已修复。

重新采集时只需复制 `tools/collect-status.py` 到原型机 `/tmp`，执行：

```sh
python3 /tmp/collect-status.py --collection-date YYYY-MM-DD
```

构建机位于远端 Windows 宿主机里的 Debian 虚拟机，SSH 入口已连通。Mesa 和 stable 内核完整构建已完成，native 内核正在构建。候选 Mesa 的包装层回归已通过；下一步仍需准备临时 native 引导并验收 Niri、物理画面和实际 core。默认部署和系统库安装需以这些验收结果为依据。
