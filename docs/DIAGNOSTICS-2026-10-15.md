# 2026-10-15 DFLL 硬件频率对照

同一 `6.12.111-moze.1-native-runtime` 内核重新使用开启 DFLL 的设备树，修正诊断服务的数据分区依赖，并在挂载后加载匹配的无线／背光模块。USB SSH、Wi-Fi SSH 与 framebuffer 均恢复，CPUFreq policy0 建立。首次未连接不能作为 DFLL 启动失败的证据；其中存在早期模块路径不可用的干扰。

但调频验收失败：powersave 请求 204,000 kHz，软件上限设为 612,000 kHz，CCF 同样显示 204 MHz；DFLL 闭环状态为 1，硬件监测却为约 1.85–1.9 GHz。只对诊断进程自身计数、绑定 CPU0 的 ARM Cortex-A15 PMU 周期测量也得到约 1.855 GHz，与软件请求明显不符。

| 读数 | 值 |
| --- | --- |
| CPUFreq 请求 | 204,000 kHz |
| DFLL 内部监测 | 1,874,250,000 Hz |
| 诊断进程用户态 CPU 周期 | 926,696,244 |
| 同段线程 CPU 时间 | 499,517,499 ns |
| PMU 估算实际频率 | 约 1,855,182,743 Hz |

PMU 只计用户态周期，时间包含少量系统开销，所以该估算不是精密校准；它足以独立否定“CPU 正在 204 MHz 运行”的结论。DFLL monitor 的上游实现按参考时钟、输出 scaler 计算实测频率，不能用 `scaling_cur_freq` 的请求缓存代替它。

本轮在启动桌面、GPU 负载和提高 CPU 上限前停止。没有手动写电压、修改 CVB 表或将候选提升为默认；默认仍是已验收的 native 内核。后续需要定位闭环、输出 scaler、PMIC I2C/LUT 与实际控制的对应关系，不能仅凭 governor 写入成功或 OPP 列表宣称调频正常。

运行时策略新增启动前硬件频率检查：稳定请求与 DFLL monitor 明显不符时，在任何 governor／上限／swap 修改前拒绝启动。六项策略回归通过，包括本轮 204 MHz 请求／1.874 GHz 实测的不匹配案例。此防护不修复 DFLL 硬件控制，也不意味着已完成降压或长期性能调教。

原型机随后按正常引导恢复 `6.12.111-moze.1-native`，用户确认桌面恢复；SSH 核对 Niri/Nyxuri 进程、背光 171/255 和两进程实际加载的最终 Mesa 路径。临时诊断服务已移除，默认内核与 DTB 哈希保持原值。

源码检查发现 Palmas SMPS 使用分段电压表，`regulator_get_linear_step()` 读取的 `uV_step` 为零；DFLL 却用它除电压索引。这是空 LUT 的候选原因，尚非实机因果验收。新的内核候选从受板级约束的有效电压项推导均匀正步长，跳过零项与重复平台，拒绝非均匀／倒序／单电压表，保持原厂 CVB 与电压范围；实际驱动函数的十项 C 回归通过。新候选仍需独立 RAM 验证，不提升为默认。

候选已完成 Image、模块、DTB、uImage 与匹配背光模块构建，release 为 `6.12.111-moze.1-native-runtime`；构建机与提交的 DFLL 源文件 SHA256 一致。构建通过不能替代调频实机验收。

| 新候选产物 | SHA256 |
| --- | --- |
| 私有测试包 | `96a6f7c9e194444277c8bd62c6b40b811953dea3d98929c08cd9f5b0999ebf9b` |
| uImage | `edd808a2e827254fa782295d0d1ceaeafca485b04dbac986b457a089fa0f239b` |
| DFLL 开启 DTB | `3ab925dfbe9c1071af0cdd4b0c121280c3e18c40de943168a7ee6faddf9820ef` |
| 匹配背光模块 | `1777303c46a1b50f2539d93915d8b852f0bb199f2f0c3a12b98169f5bc450aed` |
