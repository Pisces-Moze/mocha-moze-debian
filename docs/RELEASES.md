# 命名、版本和产物

- 人类名称：**mocha moze linux 6.12.111-moze.1**。
- Linux `UTS_RELEASE`、模块目录：`6.12.111-moze.1`。空格只用于项目名称，不加入uname。
- Makefile `NAME` 为`mocha moze linux`，CONFIG_LOCALVERSION为`-moze.1`，关闭LOCALVERSION_AUTO。
- 当前发布为源码开发快照，重新命名后的完整安装尚未重新进行端到端实机验收；不是正式成品系统。
- 多仓库release应固定内核、boot、drivers、desktop四个commit及所有构建产物SHA256。新构建不能冒用旧镜像SHA256。

历史通过的私有镜像（用于对照，不随仓库分发）：

| 产物 | SHA256 | 意义 |
|---|---|---|
| 旧uImage-desktop | 1b76bfbef11ae473d227f47b68650f9bf09dc5d94b2676e2c56b9bbe5d6b43a9 | 默认四核桌面内核，旧release名称 |
| 默认背光DT | 7b217aa0c8151615d5852152879de7a90a7971aca78ad115e30948d9cf1eccf7 | 已验证触控、GPU、背光 |
| 默认LNX前缀 | 8760cbdbc123e4350287874b9b75e6edd3d74ab78be3262b6ec2fd1175a8f7d5 | 569344字节，普通开机桌面已验证 |
| native4 uImage | 682da8b2f9a5e3a241850fd019ce5a40467f5e42e5f6e7817868a356879c7e17 | 原生DSI实验内核 |
| native6 DT | f92ee8c250fd7b06f1bec03a935182c7e92dc35232d74901199e4a3a51a9a7b3 | 链路起点纠正；桌面仍崩溃 |

公开DTS已去除本机身份、旧bootargs和initrd地址，其SHA256自然与上述历史DT不同。
项目使用GPL源码、上游链接和自己构建的产物；CUDA/MIUI固件等专有二进制不上传。
