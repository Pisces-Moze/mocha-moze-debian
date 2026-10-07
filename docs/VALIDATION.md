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
