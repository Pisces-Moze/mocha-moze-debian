# OOBE、镜像与安装工具交付复盘

这是源码和已记录实机证据的复盘，不是新镜像通过验收的声明。

## Firefox 硬解

原型默认 Firefox 153.5.1 Request 构建，通过正常启动器、独立 profile、默认偏好播放已存在的 1440×1080 Baseline 视频：RDD 日志明确记录 `V4L2 Request codec opened`、`IsHardwareAccelerated=true`、`h264_v4l2request` 和 DRM PRIME，并打开 `/dev/media0`、`/dev/video0`。这证明支持范围内的浏览器解码通路工作；不代表所有网站视频可硬解，也不代表播放性能达标。

W3Schools mov_bbb.mp4 实测为 H.264 Main，当前回退软件。驱动 `h264.c` 明确拒绝 CABAC、8×8 transform 和 field picture；Firefox SPS 门控仅允许 progressive constrained Baseline。不能通过删除门控宣称 Main/High 支持。Bilibili 必须检查实际选中的编码、SPS/PPS 和日志，不能从画质或扩展名猜测。

Baseline 短样本仍有掉帧和较高页面进程 CPU；需要单独检查呈现/缩放/直接导入，不能归因于解码本身。RSS 求和会重复计算共享内存。

同一视频经临时 localhost HTTP 服务播放也观察到 RDD 持有两个 VDE 节点；测试服务和浏览器在脚本 finally 中退出。该样本窗口未聚焦，丢帧很多，不能据此做吞吐或零拷贝性能验收。证据位于开发工作区 `artifacts/reports/firefox-http-vde-20261107.txt` 和 `firefox-http-hardware-proof-20261107.txt`，不随发行版包含。

## OOBE

已记录通过：12 项恢复故障注入、隔离根目录真实账户密码校验、实机 systemd 普通失败/SIGKILL 恢复、WebKit 隔离恢复页、Wi-Fi 新建连接及 IP 读回、已配对 ThinkBook 鼠标连接。11 月 5 日 Linux 测试结果见项目外部交接报告。

11 月 7 日实机只读复核确认 `mocha-oobe-stop.py` 存在，SHA256 `05967b9859ad47acb765f8e73e6bc4fa1b951e4149abfab390415ae9f3f585ee`；会话单元 ExecStop 使用 root 助手，pending/ready 条件已配置。未在原型上制造 pending 或修改现有账户。

剩余：新镜像首次初始化的全流程、真实新账户 PAM 登录、重启后配置保留、首次蓝牙配对（当前缺测试设备）。已有 fixture 不能代替这些验收。

## 镜像

11 月 7 日进一步修正：构建工具依赖检查移到创建输出/复制快照之前；APP 镜像改用 `mkfs.ext4 -d` 直接填充，移除 loop mount，因此无需容器 CAP_SYS_ADMIN 或 loop 设备。现有非特权 Docker 内 64 MiB fixture 已通过：内容、UID/GID、权限、硬链接、符号链接、user xattr、镜像长度和 e2fsck。该 fixture 不代替最终 3 GiB 系统镜像启动验收。额外安装 e2fsprogs，未放宽容器权限。测试源码为 tools/test-app-image.py，开发证据 ext4-fixture-20261107.txt。

静默、循环播放、预热后的 Baseline 样本仍观察到两个 VDE 节点，窗口聚焦；约 1.354 核、增量 352 帧/69 掉帧（短样本）。这只证明硬解持续工作且呈现仍需优化，不与前轮不同供电/频率/日志条件作严格性能对照。证据 firefox-quiet-warm-20261107.txt。

build-distribution.py、prepare-distribution.py、APP 3 GiB 布局、DATA 峰值容量约束和脱敏清理已有源码及测试。构建容器已补齐 rsync、ffmpeg/ffprobe、python3-cairo，使用已有签名阿里云 trixie 镜像，安装 exit 0、dpkg audit 无异常。

仍须取得最新离线只读 APP/UDA 副本和对应布局证据，外存保存，不能在仅余约 261 MiB 的原型 UDA 上生成完整快照。核对桌面、驱动、Firefox、输入法、键盘、开机资源与 GOP30 壁纸均在输入副本；排除大模型、原始重壁纸、账户凭据、配对密钥、浏览器资料和备份。构建后检查容量、所有权、权限、xattrs、依赖和哈希，再进行首启验收。当前没有证据证明最终可发布镜像已经生成。

## 一键安装

已有 Install-Mocha.cmd → flash-distribution.py → 认证 RAM 安装端的源码：bundle 七个载荷哈希、候选门控、设备几何检查、GPT/LNX 备份、APP/UDA 恢复、DATA 空间预算、LNX 最后写入和重启。断连恢复状态和容量 fixture 已有验证。

剩余：Windows 从干净环境运行、驱动/工具依赖交付、真实 RAM 安装、恢复入口与中断后续操作、新分区普通启动、OOBE 新用户初始化、锁屏解锁、网络/声音/壁纸和重启保留。只有这条链完成，才能把 bundle release_state 改为 verified。原型已有用户数据；端到端破坏性安装必须安排到具备完整回退副本的明确验收阶段。

## 推进顺序

1. 保留已工作的 Baseline Request 路径；HTTP 播放验证、实际网站编码调查、呈现性能定位。
2. 明确 CABAC/High 支持所需的软件预处理或硬件接口，优先复用开源实现；没有实现和正确性证据时保留软件回退。
3. 外部离线快照、脱敏候选构建、内容/空间核验。
4. 真实安装→OOBE→新账户→桌面完整验收，最后更新发布状态和使用教程。
