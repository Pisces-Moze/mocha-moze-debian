# Mocha Debian 镜像与安装器

当前为**未完成实机验收的候选方案**，不要作为正式发行包。系统面向已验证的 16 GB Xiaomi Mocha：APP 为 3 GiB，保留桌面、驱动及 GOP30 动态壁纸，不打包模型和原始高负载壁纸。

首次启动直接进入桌面，不运行首次设置。默认用户名和密码均为 `mocha`，主机名为 `mocha`；请进入桌面后立即运行 `passwd` 修改弱密码。root 账户保持锁定，SSH 默认关闭。Wi-Fi 和蓝牙在桌面设置中配置。

## Windows 安装

安装会格式化 APP、UDA 和 cache，**先另行备份所有个人文件**。工具保存和核验的 GPT/LNX 备份不能恢复这些文件。仅支持已验证的 16 GB 设备和受支持的 GPT 布局。

当前安装入口为 `tools/Install-Mocha.cmd`，依赖 Python 3.11+、Windows OpenSSH、Android platform-tools 中的 fastboot，以及适用的 Fastboot 和 RNDIS 驱动。候选包默认被拒绝；不能把开发模式视为正式安装。

1. 备份个人数据，给设备充电，关机后按电源＋音量减进入原厂 Fastboot，再通过 USB 直连电脑。
2. 双击 `tools/Install-Mocha.cmd`，确认擦除提示并输入 `INSTALL`。
3. 工具校验镜像、临时启动 RAM 维护环境、备份 GPT/LNX，配置分区并写入与回读校验。安装期间保持连接。
4. 完成后设备重启进入桌面；默认账户和密码均为 `mocha`，请立即更改密码。

若中途失败，请保持 USB 连接并记录错误；不要重复格式化或刷写。工具保留 RAM 维护会话以供排查。GPT/LNX 备份不能替代个人数据备份。

## 构建与验收

在 Linux root 构建环境使用已经校验的离线 APP/UDA 副本与采集证据，分别运行 `tools/build-distribution-ram.sh` 和 `tools/build-distribution.py`。构建目录、备份与源副本须分开；私有工作目录不得进入发行包。构建器会生成候选状态，不能自动标记 verified。

发布前至少验证全新目标上的完整刷写、3 GiB 分区、首次桌面、默认密码及修改密码、重启、触控、Wi-Fi、蓝牙、声音与壁纸。候选测试可使用 `flash-distribution.py image --probe --allow-candidate` 进行只读 RAM 检查；该检查不会证明刷机或桌面可用。
