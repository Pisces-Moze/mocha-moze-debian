# 接续验证：2026-10-12

接续 [10 月 11 日交接](HANDOFF-2026-10-11.md)。本轮重新读取原型机，实际仍是默认 `6.12.111-mocha-experimental-fbdiag`、simpledrm/Nouveau 与已安装的 eMMC 根文件系统；不是此前临时运行的 native 系统。没有替换默认引导或刷写分区。

APP 预存 native uImage 的 SHA256 为 `d8bc8736b124aad1ccecf097cf480d9df5be4fb9aab55bafc486e94625367e81`，DTB 为 `11e4916155e564fb2b884be6df191288997ecbad8d7863de681884718b3fab88`，与交接一致。initramfs 为 `d0a26376e1d21c4d1037af86638b9cb0f62e0bf867d968ea1ab837674c81aa65`。这次只核对文件，尚未从它们启动。

## 验收工具修复

desktop `583042e5e50afa2d850455acccc5957dfb2ea834` 修复完整会话 profile：合成器与窗口基准共享 Mesa 环境；baseline 清除继承的 native-fence 开关；从 service MainPID、maps 和对应 socket 取证。运行前检查临时 native 内核、启动参数、已启用 DSI、二进制 marker 与候选文件，保留已有 override；失败或收到可捕获的终止信号后恢复原服务。独立结果目录保留哈希、maps、journal 和帧记录。

统计器拒绝不完整记录，百分位统一为 nearest-rank；KMS 探针在 120 帧完整结束、观察到 pending fence 且恢复控制台成功后才输出 pass。

- 帧记录/百分位回归：5 项通过。
- Linux 隔离 service/proc/sysfs 回归：8 项通过，覆盖两组环境、含空格/单引号的路径、失败/TERM 恢复、陈旧 socket、旧内核拒绝和已有配置保留。分别在原型机临时目录与构建容器执行，未操作真实桌面服务。
- 真实默认系统上的 profile 前置检查拒绝运行；前后 Niri PID 均为 402，没有重启桌面。
- desktop 后续 `114138ae4b1441b569deb337ca91a2e11d2d49fd` 修复窗口基准提前关闭仍返回成功的问题，并要求结束记录包含请求的完整帧数。新增“退出码零但无完成记录”和“帧数不足”两项回归，原型机隔离环境共 10 项通过；未重启真实桌面。
- 引导工具可显式选择项目已验收的 `ram-diagnostics` 环境；默认仍要求 `charger_ready=1`。额外核对 Mocha/U-Boot 2026.07，并设置内存重定位边界和 uImage 校验。3 项模拟 Fastboot 回归通过，没有调用真实 Fastboot。

## 构建环境

旧构建虚拟机未连接，改用独立 Debian 13 amd64 Docker 容器，镜像 digest 为 `sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f`。容器限制 2 CPU、2 GiB 内存、合计 6 GiB 内存/交换空间，Niri 使用 `JOBS=1`。APT 主源、安全源及 backports 实际从清华镜像下载，配置参考 [TUNA](https://mirrors.tuna.tsinghua.edu.cn/help/debian/)；未重启主机 Docker 或改动其他服务。

工具链：Rust/Cargo 1.95.0，GCC armhf 14.2.0。Niri v26.04 官方源码归档 SHA256 为 `134c602d8e0d53413a52d6cd58f9ce7e79a07d03288ee0a51ba1abd5db1b1ad9`；官方 vendor 归档为 `407c525cd78710e72455c48741756857ca47dc32910a42f82cd40992a34beed6`，与 GitHub release digest 一致。全新源码目录使用固定 Cargo.lock，应用 0003/0009/0011、重算 vendor checksum、清理 Smithay release；构建为 locked/offline。

三项 ARMhf 探针交叉编译完成：

| 程序 | SHA256 |
|---|---|
| native-frame-timing | `7dadee2fb5216699b5e25f2ec3ef6c223324d41457db1575c3053c44bdaa8d70` |
| native-fence-test | `f35b2d3ea929f7c4cf3cd6958c6fa5b4df89d48c5107575b6accd2f44cb46eb1` |
| atomic-fence-scanout | `8448b4a80a743be67fd49a0e4b52c7d0c53d5ade164082e8950061c2f181df4b` |

新 Niri 的完整 release 编译耗时 25 分 50 秒，包含 0003/0009/0011。最初的构建后检查因容器缺少 `file` 返回 127；补齐后的一次补充调用遗漏 binary 变量，输出作废。随后以独立 `set -euo pipefail` 检查重新生成全部结果，验证退出码为 0：ARM EABI5 ELF、`KMS explicit fence capability` 和 `MOCHA_FRAME` marker 均存在，Build ID 为 `c6870b8634d723a966f335c7ee9ca4c6cd02f419`，SHA256 为 `98436b29e1d9d258674e5db9caa8712e5495e6f710ddf86bc28c987fdac439c7`。

构建机、本地下载与原型机 `/tmp` 副本的 Niri/探针 SHA256 一致；原型机 glibc 2.41 下 Niri 的 `ldd` 无缺失库，`--version` 输出 `niri 26.04 (unknown commit)`，符合使用固定上游归档而非 Git 工作树的构建方式。没有启动新合成器会话。

Mesa 25.0.7 的全新 ARMhf 构建也已完成，应用 0004..0008；构建退出码 0，DRI 链接检查通过。Gallium SHA256 为 `6d0a04e78e470a262b6b5ac8aa8697f0f0b19723e23af3b1606f766beb3ab712`，候选归档为 `8452ab8e33b77af7f1534a937c6281c19b69dda49a3664227959182e88467811`。下载和原型机解包后的哈希一致；新 Niri、Mesa、三个探针的动态库依赖均无缺失，候选 Niri 配置检查通过。

原型机已恢复 USB SSH，Wi-Fi 驱动和扫描可用；原保存网络不可见，按用户提供的新网络信息建立并验证 Wi-Fi SSH，主机密钥与已固定的 USB 密钥一致。

## 临时原生桌面验收

原厂 Fastboot 识别成功，已验证 RAM diagnostics loader 临时选择 APP 中的 native 内核；实际 SSH 为 `6.12.111-moze.1-native`，DSI 为 connected/enabled。操作没有刷写分区、saveenv 或修改默认引导，系统仍使用已安装的 rw eMMC 根文件系统。诊断启动先屏蔽用户桌面和 GPU 策略；确认墙充输入 2 A、电池 4.135 V/净充电和 GPU 46°C 后，仅在 `/run` 停用 debug generator 并解除本次诊断 mask，启动原桌面与原频率策略。此 runtime 配置随重启消失。

实机使用原 Nouveau 模块 SHA256 `f3ae72d63d06cf82123f49e707a6199e8db48fb07f3daade9862cfdd181db87d`，没有 gk20a PMU 调参参数。已安装 GPU 策略 SHA256 `742dfe2cfadf7da5dabba8c51447ca4c0bc483a270c1e8170d77347b583c818c` 与 drivers 当前源码一致。PMU 动态阈值候选没有加载，本轮结果不能作为该候选验收。

首次用 `niri-native-fencing` 名称运行测试时，策略的 `pidof niri` 失配，GPU 退回 auto；观测到 252 MHz，窗口约 30 FPS。这两组结果只用于确认同步功能，不作为 852 MHz 性能对照。desktop `ee53fac8d33b1f43404f9139c8e17eb02ea9843d` 修复测试入口，通过 runtime `niri` 链接执行候选且继续核对 `/proc/PID/exe`。重测时 `pidof niri` 与真实候选匹配，实际 pstate 观测为 852 MHz，策略保留充电、低压和热保护。

修正后的两组使用同一 Niri、不同的已校验 Mesa 候选，执行 Noctalia 控制中心/窗口概览和 600 帧 GPU 窗口测试。每组均完成并恢复正常桌面。Niri maps 的 Gallium/EGL_mesa/GBM 分别指向 WC 与新的 native-sync 目录；系统 GLVND `libEGL.so` 同时存在属正常 loader。用户确认新 native-sync 画面正常。

| 指标 | WC 对照 | native-sync |
|---|---:|---:|
| 完整 Niri 帧记录 | 1121 | 1125 |
| needs_sync=true 帧数 | 1121 | 0 |
| wait_ms 平均值 | 2.972 | 0 |
| total_ms P95 / P99 | 11.624 / 14.773 | 9.393 / 12.073 |
| 窗口 600 帧 FPS | 60.058 | 60.050 |
| 窗口 P95 / P99 ms | 17.537 / 18.699 | 17.565 / 19.338 |
| 窗口 >25 ms 帧数 | 0 | 1 |

两组都记录 `driver=tegra supports_fencing=true legacy=false`。native-sync 的 wait_ms 全部为 0；该工作负载消除了 Niri 显式 CPU wait，但 0008 的 imported server_sync 仍保留 CPU wait，不能宣称所有 GPU 同步都异步化。窗口 P99 未改善，不把 Niri profile 的改善扩大为所有应用的帧时间改善。

日志未出现 frame completion wait/queue 失败或新的 Nouveau fault/timeout、Tegra underflow。仍有启动警告：已有 WAYLAND_DISPLAY、非 master render 节点、DSI 无 EDID、缺 context-priority 扩展与缺失 xwayland-satellite；后者意味着本轮没有验收 X11 应用。蓝牙 HCI 初始化 timeout 仍存在。

desktop `dfc8c57a5a72cb2266435d16ee5b7f67dcfb96ee` 增加关闭逐帧 profile 的基准模式，显式清除继承开关，仍检查实际库、capability、完整帧数和服务恢复。含此模式的隔离回归共 11 项通过。多应用/Firefox 视频滚动/触控拖动长测、DPMS、充电器插拔与 PMU 候选仍未完成；有限会话结果不能标记为长期稳定。

关闭逐帧插桩的单轮 600 帧窗口对照：WC 59.742 FPS、P95 17.142/P99 21.345 ms，native-sync 59.747 FPS、P95 17.671/P99 19.917 ms；两组均 3 帧 >25 ms。期间实际 pstate 观测为 852 MHz，GPU 温度约 66°C，仍保留启动/capability 日志。这是连续两组有限工作负载，不代表所有应用或统计显著改善。

新 Mesa 的独立 Tegra EGL native-fence 测试通过：80 次导出/导入、80 次 pending exports，输出平均导出时间 0.059 ms，FD baseline/final 均 10，等待后像素为 `0,255,0,255`。节点通过 sysfs 核对，Tegra renderD128，Nouveau renderD129。

本轮新 KMS 探针在停止桌面后发现 `native console has no active CRTC`，前置检查返回失败并恢复桌面，没有产生新的 120 帧 pass。原先交接中的 KMS 结果保留为历史证据；新探针本轮的完整 scanout/控制台恢复验收需在活动原生控制台条件下另测，不能用编译或上述 Niri 会话代替该项。

构建标识、四组原始记录的哈希、真实候选库与统计汇总见 [本轮机器可读记录](diagnostics/2026-10-12-native-fencing.json)。原始 maps/journal、归档和二进制留在独立测试目录，未上传公开仓库。

所有本轮测试结束后，用户再次确认恢复的 Noctalia 桌面正常；SSH、DSI 和频率策略仍在线，墙充输入仍为 2 A，电量读数 86%，净充电电流约 266 mA。当前仍是临时选择的 native 内核，重启会回到原默认引导。
