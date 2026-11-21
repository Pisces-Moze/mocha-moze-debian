# OOBE 原生显示路径（2026-10-31 实机验证）

本文记录首次设置（OOBE）欢迎页从 WebKit 页面改为原生 GTK + GStreamer
零拷贝播放的实现、实测数据、构建/安装方式与已知问题。源码位于本仓库 `oobe/`：
`mocha_oobe_welcome.py`、`mocha-oobe-flow`、`build-welcome-video.py`、
`build-form-web.py`、`oobe.kdl`。

## 为什么改

原来的欢迎页是 WebKit 页面里的 `<video>`：VDE 硬解没问题，但 WebKit 合成线程
稳定吃约 1 个 CPU 核。实测定位（2026-10-31）：

- WebKit `ThreadedCompositor` 线程约 0.88 核；`.intro` 全屏
  `backdrop-filter: blur(52px)` 每产一帧重算一次；
- 暂停视频后仍高占用：`.intro-enter::after` 的 `animation: enter-pulse 2.8s infinite`
  持续产帧，使 blur 不断重算（`*` 选择器覆盖不到伪元素）；
- 把视频与伪元素全部剥离后 WebKit 降到 0.14 核；但**视频在播时 WebKit 视频合成
  本身仍约 1.0 核**，仅改 CSS 救不回视频场景。

## 架构

```
mocha-oobe-session.service (tty1, user mocha)
  └─ mocha-oobe-session (dbus-run-session niri --config /etc/mocha/oobe.kdl)
       └─ spawn-at-startup: /usr/local/libexec/mocha-oobe-flow
            ├─ ① mocha_oobe_welcome.py
            │     GTK3 透明全屏窗口 + gtkwaylandsink
            │     filesrc ! qtdemux ! h264parse ! v4l2slh264dec ! gtkwaylandsink
            │     VDE 输出 DMABuf/YU12 → Wayland 子表面（零拷贝，无 GL 客户端工作）
            │     循环 3–18 s，按钮点击后播放 18–19.5 s 离场段
            │     按钮视觉已烘焙进视频；GTK 按钮仅作触摸热区
            │     管线置 PAUSED、隐藏窗口并保持进程存活
            ├─ 标记文件通知交接（不再固定等待 5 秒）
            └─ ② mocha-oobe-ui.py --web-root …/form-web
                 现有 WebKit 表单外壳 + build-form-web.py 生成的表单树
```

## 实测指标（Mocha 2048×1536，niri scale 1，VDE 硬解，30 fps 视频）

| 场景 | 应用 CPU | niri CPU | 合计占用 | 视频 fps | 可用内存 |
|---|---|---|---|---|---|
| WebKit 预制欢迎视频（原方案） | WebKit 1.05 + 宿主 0.21 | 0.14 | ~45% | 30.0 | 889 MiB |
| GTK3 + gtkglsink | 1.05–1.13 | 0.12–0.27 | ~36–46% | 29–30 | ~960 MiB |
| **GTK3 + gtkwaylandsink（本方案）** | **0.26** | **0.03** | **20–25%** | **29–30** | **1050–1080 MiB** |
| 表单页（静态背景 + 去实时模糊） | WebKit 0.01–0.02（加载爆发后） | 0.14 | 7–14% | — | ~720 MiB |

其他验证：循环与离场正常；`/dev/uinput` 注入点击可命中热区。早期销毁管线时观察到
可用内存 +400 MiB，但该路径伴随合成器崩溃，不能用于正式流程；现方案保留暂停的欢迎
进程到专用会话结束，尚未重新测定其内存保留量。GTK4 + gtk4paintablesink 方案实测不可用（GTK 4.18 在 YUV
DMABuf 纹理路径崩溃；回退 RGBA 后主线程 1.46 核），已放弃。

## 构建

构建主机（Debian 13 amd64）执行，需要 `python3-cairo`、`ffmpeg`（含 libx264）、
`node`（构建批准网页资源，见 build-web.py 的既有流程）。

```sh
# 1. 批准网页资源（既有流程）
python3 oobe/build-web.py --output build/oobe-web

# 2. 烘焙欢迎视频：把按钮与脉冲合成进批准动画（约 1-3 分钟）
#    源必须是批准导出的欢迎视频（1920x1080 SAR 3:4，30fps，19.5s）
python3 oobe/build-welcome-video.py \
    --source build/oobe-web/assets/<approved-intro>.mp4 \
    --output build/oobe-welcome/intro-baked.mp4

# 3. 表单树：跳过 WebKit 内 intro，静态背景 + 去实时模糊
python3 oobe/build-form-web.py --source build/oobe-web --output build/oobe-form-web
```

产物校验：烘焙视频必须是 **Constrained Baseline / CAVLC**（Tegra124 VDE 只解该档；
High/CABAC 会停在 1 帧）、1440×1080 方像素、30 fps、19.5 s——构建脚本会断言。

## 安装（rootfs 内）

| 文件 | 目标 |
|---|---|
| `oobe/mocha_oobe_welcome.py` | `/usr/local/libexec/mocha_oobe_welcome.py`（0755） |
| `oobe/mocha-oobe-flow` | `/usr/local/libexec/mocha-oobe-flow`（0755） |
| `oobe/mocha-oobe-stop.py` | `/usr/local/libexec/mocha-oobe-stop.py`（0755，服务 ExecStop） |
| `build/oobe-welcome/intro-baked.mp4` | `/usr/local/share/mocha-oobe/welcome/intro-baked.mp4` |
| `build/oobe-form-web/` | `/usr/local/share/mocha-oobe/form-web/` |
| `oobe/oobe.kdl` | `/etc/mocha/oobe.kdl` |

依赖：`python3-gi`（Gtk 3.0 / Gdk 3.0）、`gir1.2-gstreamer-1.0`、`gstreamer1.0-plugins-bad`
（gtkwaylandsink）、`gstreamer1.0-plugins-base`（qtdemux/h264parse）、内核 VDE
（`v4l2slh264dec`）。表单树仍需既有的私有 metabridge 插件目录（`mocha_oobe_shell`
的启动校验要求其存在），即使表单页不播视频。

## 开发 / 验证模式（不改变正式行为）

桌面会话验证时不要强制把 DSI-1 改成 scale 1：那会让桌面光标变小，并让 WebKit 表单
按 2048×1536 全分辨率渲染，实机观感卡顿。两种辅助方式：

- `mocha_oobe_welcome.py --windowed`：欢迎页以 1200×900 窗口运行，不接管全屏；
- 表单外壳：`MOCHA_OOBE_WINDOWED=1` 环境变量，同样改为窗口运行。

窗口化模式下 DOM/触摸/交接逻辑与正式模式一致，只降低渲染与合成负载；正式验收仍需
在 OOBE 专用 Niri（`oobe.kdl`，scale 1）里跑全屏。

另：曾试过"OOBE 内部按 1× 渲染、合成器放大到物理屏"（桌面 scale 1.5 + GDK_SCALE=1）
来降低负载，实测**更差**：画面明显变软，niri 因放大/混合升到约 0.47 核、总占用约 31%
（物理分辨率渲染时为 20–25%），因此不采用。

## 已知问题 / 待办

1. **任何 waylandsink 客户端断开都会让 niri 合成器崩溃（SIGABRT）** —— 2026-11-01 实机定位：
   niri 日志出现 `GL_INVALID_VALUE in glTexSubImage2D(yoffset 0 + height 2000 > 1908)`、
   EGL 错误，随后 `corrupted double-linked list` 并 abort。裸 `gst-launch … ! waylandsink`
   即可复现（与 GTK 无关）；SIGTERM 与 SIGKILL 都会触发。**WebKit 表单进程断开是安全的**
   （实测 niri 稳定）。此前的"表单黑屏、缩放回跳、桌面卡顿"多数是合成器崩溃重启造成的
   假象，不是 WebKit 性能问题。
   现行设计（已实机验证）：欢迎进程在离场后**保持存活**（PAUSED + 隐藏窗口、不销毁子表面），
   launcher 读到标记文件后立即启动表单进程；OOBE 以**重启**或**停止会话**收尾（session 先停
   niri 再停客户端）。2026-11-01 源码修正：不能用整组 SIGKILL 声称保证退出顺序；
   `ExecStop` 读取服务 MainPID 所在 cgroup（兼容 PAM/logind 移入独立 scope），以 pidfd
   锁定使用 `/etc/mocha/oobe.kdl` 的 niri，单独终止并等待退出，再由 systemd 清理客户端。
   专用真实 OOBE 会话和 apply 交接仍需实机验收；异常/超时路径可能回退 systemd 的组清理。
   GL 错误与堆损坏的具体责任源码尚未定位，不能据此认定上游某个组件已确认存在根因。
   launcher 不做任何 kill/trap。
   **禁止**在 OOBE 会话运行期间停止/杀死欢迎进程。
2. 表单页加载后约 5–10 s 内 WebKit CPU 有 ~0.9 核的启动爆发，随后回落到 ~0.01 核，
   原因待查（疑似页面首次上屏/动画缓存）；欢迎视频路径本身只有约 0.26 核。
3. 表单静态背景 + 实时 `backdrop-filter` 会让 WebKit 表单黑屏（需在静态背景上预烘焙
   模糊，不可恢复实时 blur），因此表单树禁用实时模糊、卡片改近不透明填充。
4. 脉冲周期由设计的 2.8 s 调整为 3.0 s，使 3–18 s 循环段恰好包含 5 个完整脉冲
   （无缝循环）；视觉差异不可感知。
