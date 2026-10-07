# 固定来源

| 项目 | 基线/出处 | 使用方式 |
|---|---|---|
| Linux | Debian linux-source-6.12，Makefile 6.12.111 | 完整源码快照，保留 COPYING/LICENSES；Mocha 源码修改单独提交 |
| U-Boot | https://source.denx.de/u-boot/u-boot ，v2026.07 | clone 固定 tag，覆盖仓库 overlay 后构建 |
| 厂商源码 | https://github.com/MiCode/Xiaomi_Kernel_OpenSource ，mocha-kk-oss，`79b4898e25fe3b506ff902e182b47068598c838a` | TLK/SMP、面板、PMIC、USB、音频、触控依据 |
| 社区 Mocha | https://github.com/Insei/linux ，`1e3857d7a1ea87cd2cc15eca2d36f57cb591c4bf` | 早期板级/面板参考，后续逐项对照官方与实机 |
| Niri | https://github.com/niri-wm/niri ，v26.04 | ARMv7 构建，Smithay `ff5fa7df392cecfba049ffed55cdaa4e98a8e7ef` 旋转损伤补丁 |
| Noctalia | https://github.com/noctalia-dev/noctalia ，v5.2.1 | 此版本为 C++/Meson 项目；不混用旧 QML shell 的安装方式 |
| Mesa | Debian 25.0.7-2+deb13u1 | 默认渲染与 native 崩溃证据；不发布 NVIDIA 用户态库 |
| CUDA/Gdev | 原厂 CUDA 6.5 包和实验 Gdev 兼容层 | 示例/接口检查；完整运行时未通过 |

官方 MIUI V9.2.4.0 固件包与原设备固件只用于对照和私有提取，不随仓库分发。
构建版本和固定 SHA256 另见 `manifests/source-provenance.json`。外部 GPL 源码的版权头必须保留。
