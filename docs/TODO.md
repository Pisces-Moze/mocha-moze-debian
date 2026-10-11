# 未完成任务（2026-10-11 交接）

从 [远端交接](HANDOFF-2026-10-11.md) 接续。打勾只表示有明确验证证据，不以编译/枚举成功代替功能验收。

## 当前下一步：原生显示稳定性与同步

- [x] Tegra 双 DSI 自动左右分段、原生 Niri/Noctalia、触控和亮度的有限实机检查。
- [x] Mesa 空 fence/reset 回调、旋转 scissor、modifier alias、GK20A WC 图片/堆/上传缓冲源码及回归工具已整理。
- [x] 墙充 852 MHz 受控窗口测试约 60 FPS；记录 P95/P99 和观测开销。
- [x] 独立异步输出 sync_file + KMS IN_FENCE_FD 测试通过；没有 CPU 像素复制。
- [ ] 完成 0009 Smithay 新构建；核对二进制 marker/哈希，不采用截断或旧构建缓存。
- [ ] 完整 Niri 验证 `supports_fencing=true`、`needs_sync=false`、wait_ms=0；对照帧时间并核对实际加载库。
- [ ] 对多窗口、Noctalia 动画、Firefox 视频/滚动、触控拖动做稳定性与 P95/P99 对照。
- [ ] 定位间歇黑屏/重启/SSH 失联，区分供电、温度、GPU hang、显示恢复与文件系统因素；不再盲目重复热卸载 Nouveau。
- [ ] 用户空间充电/热策略完整冷启动、DPMS、充电器插拔与电池状态验证，随后才考虑默认原生引导。
- [ ] PMU 动态阈值调参候选只在 RAM 验证；当前 60 FPS 结果不依赖它。超频/新增电压表后置。
- [ ] 改善 imported fence 的 GPU server-wait 路径；当前导入 server_sync 仍使用保守 CPU wait。
- [ ] 对 modifier alias 的格式/stride/layout 边界继续验证，不把一次 scanout 成功当作所有 tiled 格式兼容。

## 用户此前指定：扬声器 → 桌面卡顿 → CUDA Runtime

- [ ] 扬声器/麦克风：RT5671 0x1c NACK 未解决。对照官方 MIUI 的上电、reset、I2C、MCLK、codec-master 与路由；TFA9890 revision 可读，但 ALSA 无卡。保留工厂 MTP，不能以 PipeWire 服务运行替代真实发声/录音。
- [ ] CUDA Runtime：Gdev 的有限 Driver API 整数计算通过，libcudart 6.5 error 35 未解决。核对 R21.x ARMhf ABI、driver/runtime 版本与 ioctl；不要用官方闭源库替换现代桌面栈，也不要把专有包上传公开库。
- [ ] 视频硬件编解码：软件 FFmpeg/Firefox H.264 可用，Tegra124 硬解/编码尚未实现；调查现有上游/开源方案与官方 MIUI/L4T 接口，分别测正确性、吞吐和 CPU 占用。

## 系统与外设

- [ ] 现代内核蓝牙 HCI、扫描、配对、连接及音频完整验收；BlueZ 菜单可打开不代表硬件完成。
- [ ] 摄像头传感器、ISP、媒体图及采集；USB OTG VBUS/外设；休眠与恢复。
- [ ] 完整规范化安装路线的端到端验收、APP/UDA 容量方案与分区扩容教程。没有改 GPT，不能宣称已扩容。
- [ ] 充电模式持久开机规则、电源键直进桌面及实际电量回升长测；充电 UI 正常与桌面净充电分别核对。
- [ ] 默认 simpledrm 与原生候选的文档/配置迁移；候选合并前保留可回退引导。

后续改动优先利用已存在的开源驱动/合成器资源，并在实机确认关键结果；源码提交、构建通过、设备枚举、屏幕实际显示和长期稳定分别记录。
