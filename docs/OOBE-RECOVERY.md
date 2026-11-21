# 首次设置的失败恢复

账户设置由 root 服务应用，网页收到的确认只表示请求入队，不代表初始化完成。密码不进入命令参数、进度文件或网页恢复状态。

## 提交和交接

1. 后端校验用户名、计算机名、语言、时区和密码，用标准 SHA-512 crypt 生成密码哈希；通过私有 UNIX socket 仅接收预置 UID 1000 的请求。
2. `request.json` 和 `progress.json` 以临时文件、fsync 和原子替换保存。请求文件为 0600，状态接口只返回非秘密选项。
3. apply 先检查依赖、语言资源和用户名冲突，再停止设置会话、改名、安装密码、保留硬件权限组并应用主机名、语言及时区。停止会话沿用先停 Niri、再清理欢迎视频客户端的顺序。
4. 读回账户、密码哈希、sudo 组、计算机名、语言和时区后，写入绑定本次请求摘要的 `handoff-ready.json`。正常桌面的首次启动门控接受这个 root 标记；此时仍保留 `pending`。
5. 桌面服务启动成功，或 getty 路径中用户的 Niri 确认 active 后，才写完成状态并移除 `pending`。getty active 本身不能判作桌面已就绪。

## 失败和断电

- apply 非零退出、超时或被信号终止，systemd `OnFailure` 启动 `mocha-oobe-recover.service`。
- 恢复服务保留请求，清除未完成的桌面交接标记，记录 `failed`，按 UID 1000 的实际登录名修复服务和权限规则的引用，然后重启设置后端及设置会话。
- 重新打开表单时恢复用户名、计算机名、语言及时区；密码与确认密码清空，要求重新输入。状态查询有有限重试，不能读到状态时明确提示。
- 已知失败不会在每次开机自动重放。中断但未记录失败的请求会恢复处理；只有匹配请求摘要的 ready 标记才允许跳过已完成的配置阶段。
- 完成标记提交之后的清理错误不会再次终止已启动的桌面。初始化不会回滚到出厂密码，也不会删除用户文件。

## 网络与显示

Wi-Fi 成功需要无线设备和活动连接均已激活，并获得有效 IPv4 或全局/ULA IPv6；仅关联到 AP 不算成功。失败只清理本次新建 UUID。蓝牙 Connect 后检查 Connected，支持时还检查 ServicesResolved；配对串行化，清理回调不能影响下一次操作。扫描时 BlueZ 返回 `InProgress`（其他客户端已占用发现）不再吞掉设备列表，仍读取 ObjectManager 并下个快照重试。

表单使用静态背景、预制资源和不透明卡片，禁用媒体和实时模糊。WebKit 在媒体禁用时可能把 `<video>` 作为普通元素暴露；表单 hook 必须移除隐藏视频，不能无条件调用 pause/load 而中断后续原生通信。用户批准的 `oobe/preview` 不由这些优化覆盖。

## 验证范围（2026-11-01）

### 2026-11-07 实机安装清单补正

逐项对比源码和实机发现会话启动器缺失，flow/UI/network 三个文件未同步。已在确认 OOBE inactive、无 pending 后，保存到 `/var/backups/mocha-oobe/runtime-sync-20261107`，补齐会话脚本并同步三个文件；shell/Python 语法校验后原子替换，未启动 OOBE、未修改账户。第二次校验 15 项文件哈希全部匹配。下表中“无法经 SSH 确认 stop helper/安装清单”属于此前状态，已由本次实际核对取代；首启、真实新账户登录和首次蓝牙配对仍未验收。

| 检查 | 结果与边界 |
|---|---|
| 12 项 Python 故障注入 | 通过；模拟账户/服务命令 |
| 隔离 Linux 根目录真实改名及密码校验 | 通过；使用实际 usermod/chpasswd/NSS，桌面命令仍模拟 |
| 实机 systemd OnFailure | 通过；普通异常及 SIGKILL，使用隔离状态和占位会话，未修改 owner 账户 |
| 实机 WebKit 恢复页面 | 通过；真实桥接到私有只读状态 socket，非秘密字段恢复且密码为空 |
| 实机 Wi-Fi 已有连接 | 通过；UID 1000 读回状态和 IP，不新增配置 |
| 实机 Wi-Fi 新建连接 | 通过；UID 1000 调用 AddAndActivateConnection 并取得 IP；支持合法 64 位十六进制 PSK，结束恢复原配置并清理专用测试 UUID |
| 实机 ThinkBook 鼠标 | 通过；UID 1000 的 OOBE 后端连接，Connected/ServicesResolved 为真 |
| 2026-11-05 复跑 12 项 Python 故障注入（Windows / Python 3.14） | 通过 |
| 2026-11-05 复跑 11 项网络 mock（Wi-Fi / 蓝牙） | 通过；新增 BlueZ `InProgress`（其他客户端占用发现）时仍列出设备列表的边界 |
| 2026-11-05 复跑前端恢复（Node，native.js DOM mock） | 通过；已填非密码字段恢复、密码清空、queued 不显示假完成 |
| 2026-11-05 复跑发行版清理测试 | 3 项通过；Linux-root 隔离改名测试按平台跳过（2026-11-01 已在 Linux 通过 4 项，含 systemd-analyze 条件） |
| 2026-11-05 systemd 故障恢复测试 | Windows 上按设计拒绝（需 Linux root `--fixture`）；本轮未重跑，2026-11-01 实机 OnFailure 已通过 |
| 首次蓝牙配对（扫描→选择→配对码确认→Connected/ServicesResolved 读回→失败重试/超时） | **待实机验收**：当前无可用配对设备；已配对鼠标连接通过，离线逻辑与 60 s 配对码超时/105 s 总超时已有 mock 覆盖 |
| 原型机 OOBE 安装清单（单元/模块/form-web、`ExecStop` 助手是否存在） | **待实机核对**：2026-11-01 安装脚本已写入单元与模块，但清单不含 `mocha-oobe-stop.py`；无 SSH 无法确认文件存在 |

这些检查不能代替最终镜像中专用 OOBE 会话的完整首次初始化、PAM 登录和刷机验收。禁止在已经初始化的用户系统创建 `pending` 来模拟出厂设置。2026-11-05 的复跑只在本工作站执行，未改动平板。原型机在 2026-11-01 通过安装脚本（未设置 `pending`、未重启 owner 设置、校验 source hash）写入恢复版 OOBE 单元/后端/状态模块并替换 form-web，备份在 `/var/backups/mocha-oobe/recovery-20261101-153634`；单元未 enable，`pending` 不存在时条件不满足。该安装脚本清单未包含 `mocha-oobe-stop.py`（session ExecStop 助手），本轮无法经 SSH 核对，列为待实机检查项。Firefox 候选的默认安装属于上一轮原型机行为，不代表镜像已验收。

开发者可运行 `python3 tools/test-oobe-recovery.py`、`node tools/test-oobe-native-recovery.cjs`、`python3 tools/test-oobe-network.py` 和 `python3 tools/test-distribution.py`。真实 systemd 测试需 Linux root 显式运行 `python3 tools/test-oobe-systemd-recovery.py --fixture`；它只创建带独立名称的临时服务，拒绝在真实首次设置尚未完成的系统运行，并在结束后删除测试服务；非 Linux 平台会以 `Explicit root --fixture required` 清理拒绝而不是抛出 AttributeError。
