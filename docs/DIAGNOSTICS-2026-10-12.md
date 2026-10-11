# 接续验证：2026-10-12

接续 [10 月 11 日交接](HANDOFF-2026-10-11.md)。本轮重新读取原型机，实际仍是默认 `6.12.111-mocha-experimental-fbdiag`、simpledrm/Nouveau 与已安装的 eMMC 根文件系统；不是此前临时运行的 native 系统。没有替换默认引导或刷写分区。

APP 预存 native uImage 的 SHA256 为 `d8bc8736b124aad1ccecf097cf480d9df5be4fb9aab55bafc486e94625367e81`，DTB 为 `11e4916155e564fb2b884be6df191288997ecbad8d7863de681884718b3fab88`，与交接一致。initramfs 为 `d0a26376e1d21c4d1037af86638b9cb0f62e0bf867d968ea1ab837674c81aa65`。这次只核对文件，尚未从它们启动。

## 验收工具修复

desktop `583042e5e50afa2d850455acccc5957dfb2ea834` 修复完整会话 profile：合成器与窗口基准共享 Mesa 环境；baseline 清除继承的 native-fence 开关；从 service MainPID、maps 和对应 socket 取证。运行前检查临时 native 内核、启动参数、已启用 DSI、二进制 marker 与候选文件，保留已有 override；失败或收到可捕获的终止信号后恢复原服务。独立结果目录保留哈希、maps、journal 和帧记录。

统计器拒绝不完整记录，百分位统一为 nearest-rank；KMS 探针在 120 帧完整结束、观察到 pending fence 且恢复控制台成功后才输出 pass。

- 帧记录/百分位回归：5 项通过。
- Linux 隔离 service/proc/sysfs 回归：8 项通过，覆盖两组环境、含空格/单引号的路径、失败/TERM 恢复、陈旧 socket、旧内核拒绝和已有配置保留。分别在原型机临时目录与构建容器执行，未操作真实桌面服务。
- 真实默认系统上的 profile 前置检查拒绝运行；前后 Niri PID 均为 402，没有重启桌面。
- 引导工具可显式选择项目已验收的 `ram-diagnostics` 环境；默认仍要求 `charger_ready=1`。额外核对 Mocha/U-Boot 2026.07，并设置内存重定位边界和 uImage 校验。3 项模拟 Fastboot 回归通过，没有调用真实 Fastboot。

## 构建环境

旧构建虚拟机未连接，改用独立 Debian 13 amd64 Docker 容器，镜像 digest 为 `sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f`。容器限制 2 CPU、2 GiB 内存、合计 6 GiB 内存/交换空间，Niri 使用 `JOBS=1`。APT 主源、安全源及 backports 实际从清华镜像下载，配置参考 [TUNA](https://mirrors.tuna.tsinghua.edu.cn/help/debian/)；未重启主机 Docker 或改动其他服务。

工具链：Rust/Cargo 1.95.0，GCC armhf 14.2.0。Niri v26.04 官方源码归档 SHA256 为 `134c602d8e0d53413a52d6cd58f9ce7e79a07d03288ee0a51ba1abd5db1b1ad9`；官方 vendor 归档为 `407c525cd78710e72455c48741756857ca47dc32910a42f82cd40992a34beed6`，与 GitHub release digest 一致。全新源码目录使用固定 Cargo.lock，应用 0003/0009/0011、重算 vendor checksum、清理 Smithay release；构建为 locked/offline。

三项 ARMhf 探针交叉编译完成：

| 程序 | SHA256 |
|---|---|
| native-frame-timing | `81d196ce80706063273a6b63d03885f7dfd21aa8c8a30c10274c4a7fb29a810b` |
| native-fence-test | `f35b2d3ea929f7c4cf3cd6958c6fa5b4df89d48c5107575b6accd2f44cb46eb1` |
| atomic-fence-scanout | `8448b4a80a743be67fd49a0e4b52c7d0c53d5ade164082e8950061c2f181df4b` |

新 Niri 的完整构建、二进制 marker/Build ID/哈希与完整原生会话同步验证仍待完成。静态检查、隔离回归和交叉编译不能标记为新合成器实机验收。
