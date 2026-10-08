# 此次整理与发布的验证范围

2026-10-08发布验证针对源码和安装资料；按用户要求暂停实机开发，本次没有重启、刷写或更改平板。

| 检查 | 结果 | 实际范围 |
|---|---|---|
| Linux完整源树 | 86,744个Git跟踪文件 | Debian原始基线、Mocha变更与规范化构建提交分离 |
| 两种设备树 | stable-desktop/native-experimental均由dtc生成DTB | 警告保留；编译成功不代表外设运行完成 |
| stable内核配置 | olddefconfig通过，kernelrelease=6.12.111-moze.1 | 没有重新构建并刷机验收整个新命名内核 |
| 充电UI | ARM交叉编译通过 | 原机此前竖屏充电/按键已实测；新统一安装路径未重刷 |
| DMA-BUF色块、CUDA probe | ARM交叉编译通过 | 之前实机色块可见/有限CUDA计算通过，不代表完整桌面或runtime |
| Android U-Boot封装器 | 已用实际U-Boot ELF/payload检查头部、长度、载入字段和SHA1 | 新容器名称导致哈希变化，没有新刷机验收 |
| 脚本、配置 | 逐个shell语法、Python AST、TOML/JSON解析 | 构建依赖配置核对实际Linux VM资料；规范化安装未端到端跑完 |
| 多仓库来源 | 上游tag/revision、Linux源压缩包SHA256、四仓库commit锁 | 上游下载仍需网络，构建产物需开发者自己计算哈希 |
| 公开内容筛选 | 项目文件排除凭据、设备备份、校准、专有固件和编译镜像 | 上游Linux测试样例仍保持原始源码，不能按字符串判定为私人凭据 |
| GitHub上传 | 五个public仓库，远端main与本地提交逐一对照 | repos.lock.json锁定其余四仓库的配套版本 |

不能把本表的静态/交叉编译验证称为“新版本已可一键刷入”。参考[安装指南](INSTALL.md)逐级RAM、APP、LNX验证；待解决的问题在[ISSUES.md](ISSUES.md)。

## 2026-10-09 继续诊断

- USB SSH 实际读取旧内核、四核、DRM、ALSA、蓝牙、电源和存储状态；未重启或写 APP/LNX。采集脚本只读取白名单字段，不收集设备身份、命令行、环境变量和任意 journal 内容。
- 原有 Mesa / Nouveau / NVEA 的 32 轮 EGL fence 跨上下文等待和红/绿像素检查通过；未覆盖 Tegra 包装层，也未观察面板。
- Mesa 官方 25.0.7 归档 SHA256 校验、补丁 hunk 检查与主机 C 回归完成：原始源码失败，候选源码的八种回调组合通过，转发参数检查通过。Debian 13 上完整 ARMhf 交叉构建已通过。
- 同一原型机用独立 EGL probe 强制 Tegra 包装层，在 `eglWaitSyncKHR` 重现 SIGSEGV。GDB remote 的 PC/R3 为零，实际 Thumb BLX R3 指令、LR 的 `+0xd645bc` 与运行库 Build ID 均与历史 Niri 调用点吻合；未切换 native 内核或改变现有桌面。
- 候选 Mesa 在同一原型机的独立数据目录运行，Nouveau 与 Tegra 包装层均通过 32 轮 EGL fence 和像素检查。实际加载的三类 Mesa 库均来自候选目录，Tegra 不再 SIGSEGV；原有桌面仍运行。native KMS、Niri、面板与 zero-copy 验收仍待完成。
- `/proc/config.gz` 确认运行内核关闭 `CONFIG_ELF_CORE`。公开 stable/native 配置已启用并增加构建断言；两份配置的 `olddefconfig` 均保留三个 core 前提选项，stable 的 Image/uImage、模块和 DTB 完整构建通过。native 编译、临时启动和实际 core 捕获仍待完成。
- 新 Python 工具语法、Meson cross file 解析通过；板上 `--require-tegra` 正确拒绝 Nouveau 节点。

具体状态、验证边界和下一步见 [诊断记录](DIAGNOSTICS-2026-10-09.md) 与 desktop 仓库的 [MESA-FENCE.md](https://github.com/Pisces-Moze/mocha-moze-desktop/blob/main/docs/MESA-FENCE.md)。
