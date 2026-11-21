# 本地 OOBE 运行素材

此目录保存由已确认网页导出的运行素材。视频和个人图片不写入 Git 历史，构建镜像时从本地素材目录读取；源码仓库本身不包含完整镜像载荷。

需要以下文件：

- `background.mp4`：1920×1080、30 fps、H.264 Constrained Baseline／CAVLC、单参考帧、无 B 帧、GOP30。校验值见 `../approved-design.json`。
- `intro-landscape.mp4`、`intro-landscape.png`、`intro-start.png`、`background-poster.jpg` 和 `intro.json`：通过 `../../tools/render-oobe-intro.mjs` 生成。欢迎页按 2048×1536 设计，编码栅格为 1920×1080，运行时恢复页面比例。

渲染器在构建电脑逐帧执行原始网页，再合成视频。仅将上述最终输出复制到此目录；无损中间片、浏览器缓存、Node 依赖不进入镜像。详细配置见 [封装文档](../../docs/DISTRIBUTION.md#欢迎动画预制)。

`../build-web.py` 检查预制视频尺寸声明与 SHA-256，输出独立运行目录。实机欢迎页不计算粒子或文字漂浮，离场后卸载欢迎视频，再启动设置页背景视频。表单、触屏键盘和网络设置仍是可交互组件。
