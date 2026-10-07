# 原工作区文件整理

公开仓库采用复制、筛选和脱敏，不删除历史原件。

| 原目录/材料 | 新仓库位置 | 处理 |
|---|---|---|
| Linux Debian原始源码 + /opt/mocha/kernel-6.12 | linux完整源码、moze/source-provenance.json | 上游基线提交与Mocha变更提交分离 |
| 最终uboot-dsi-quiesce.c、panel-vendor-sequence、default env | boot/overlay、configs | 选最终冷启动通过版本；不使用测试结束恢复的旧源码 |
| 桌面backlight、audio、touch源码 | drivers/backlight、audio、touch | 稳定与experimental明确分开 |
| native DMA-BUF / EGL / frame / CUDA自检 | drivers/diagnostics、cuda | 保留可复核工具和未完成说明 |
| Niri Smithay补丁、Noctalia配置 | desktop/patches、config | 固定上游tag和vendored revision |
| 充电C UI、BC1.2检测、服务 | desktop/charging | 路径规范化；保留输入电流与电池电流区别 |
| rootfs/RAM安装方法 | debian/tools、ramdisk、docs | 去掉私人主机地址、设备序列号和授权密钥 |
| 原机GPT/boot/system/UDA镜像、Wi-Fi密码、SSH私钥 | 不进入公开仓库 | 私有原件保留 |
| MIUI/CUDA/无线固件、完整开发虚拟机 | 不进入公开仓库 | 记录来源与提取方法 |
| 早期大量失败镜像与日志 | 本地历史；公开ISSUES摘要 | 不作为默认配置、不上传含身份的原始日志 |

后续实验按“候选源码→临时实机→结果→默认提升”流程。不要因目录名含candidate就假定当前文件仍是实际测试版本，构建脚本可能用trap恢复源码。
