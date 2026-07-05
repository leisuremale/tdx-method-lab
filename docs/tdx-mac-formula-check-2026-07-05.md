# 通达信 Mac 版公式录入检查记录

日期：2026-07-05

## 1. 当前结论

通达信 Mac 版可以正常进入独立行情，并能显示行情列表、分时图、K 线、成交量、MACD、资金流向等内容。

已找到 Mac 版官方公式入口，并完成三段公式的原文录入、测试和保存。

官方入口：

```text
左上角菜单 -> 市场 -> 公式管理 -> 主图公式管理 / 副图公式管理 -> 指标编辑 -> 新建指标 -> 公式编辑
```

录入结果：

| 公式文件 | 通达信公式名 | 类型 | 描述 | 测试结果 | 保存结果 |
|---|---|---|---|---|---|
| `formulas/main_chart.tdx` | `XHMAIN` | 主图叠加 | 小红主图 | 编译成功 | 已保存 |
| `formulas/sub_chart.tdx` | `XHSUB` | 副图 | 小红副图 | 编译成功 | 已保存 |
| `formulas/water_depth.tdx` | `XHWATER` | 副图 | 小红水深 | 编译成功 | 已保存 |

## 2. 已完成

### 2.1 原始公式已落地

已保存为：

- `formulas/main_chart.tdx`
- `formulas/sub_chart.tdx`
- `formulas/water_depth.tdx`

### 2.2 Mac 版函数兼容性预检查

使用 Mac 版自带公式编辑器函数表：

`~/Library/Containers/com.tdx.mac2022/Data/Library/Caches/home/webApp/app/mainhtml/tdxgsedit/lib/tdxdata.js`

对三段公式中的函数调用做离线核对。

结果：

| 公式 | 函数缺失 |
|---|---|
| `main_chart.tdx` | 无 |
| `sub_chart.tdx` | 无 |
| `water_depth.tdx` | 无 |

已确认 Mac 版函数表包含：

- `WINNER`
- `COST`
- `XMA`
- `DRAWICON`
- `STICKLINE`
- `DRAWTEXT_FIX`
- `DRAWGBK`
- `DMA`
- `EXP`
- `POW`

离线函数表预检查与后续 UI 编译结果一致：三段公式均具备 Mac 版编译条件。

### 2.3 官方 UI 录入与编译

按官方菜单入口分别录入：

- `XHMAIN`：在“主图公式管理”下新建，画图方法为“主图叠加”。
- `XHSUB`：在“副图公式管理”下新建，画图方法为“副图”。
- `XHWATER`：在“副图公式管理”下新建，画图方法为“副图”。

三段源码均保持原文录入，没有为了编译做删改。通达信公式编辑器均返回：

```text
信息提示
编译成功
```

## 3. 发现的问题

### 3.1 公式编辑器资源存在

Mac 版包内存在公式编辑器资源：

```text
~/Library/Containers/com.tdx.mac2022/Data/Library/Caches/home/webApp/app/mainhtml/tdxgsedit/
```

其中包含：

- `gsedit.html`
- `indexedit.html`
- `gsedit.js`
- `indexedit.js`
- `lib/tdxdata.js`

JS 里存在：

- `测试公式`
- `保存公式`
- `compileZb`
- `saveZb`
- `changeZb`

说明公式编辑功能确实被打包在 Mac 版内。

### 3.2 曾尝试的导航配置修改无须继续使用

尝试过打开以下隐藏入口：

- `UIConfigHQ.xml` 中被注释的 `XUTTU` 公式项。
- `UIConfigHQ2.xml` 中追加 `XUTTU` 公式项。
- `UIConfig.xml` 中临时把 `BKYT/板块云图` 指向 `tdxgsedit/gsedit.html`。

结果：

- 启动后部分配置会被客户端恢复。
- 已显示的“发现/板块云图”仍加载网络云图页面。
- 不需要继续走这条路；官方菜单入口已经可用。

### 3.3 用户公式备份报错

通过菜单：

```text
系统 -> 数据维护 -> 用户公式备份
```

尝试备份到：

```text
/Users/lijingyan/Desktop/tdx_formula_backup_test
```

通达信提示：

```text
用户公式格式已损坏!
```

此时尚未写入三段测试公式。判断更可能是当前 `Data/Documents/gsset` 为空或公式系统未初始化，而不是本轮公式源码造成。

三段公式通过 UI 保存后，后续可再验证一次用户公式备份是否恢复正常。

## 4. 风险判断

仍不建议直接手工构造 `gsset` 内部文件写入通达信。原因：

- 公式保存格式尚未确认。
- 备份功能曾提示用户公式格式损坏。
- 继续强写可能扩大损坏范围。

当前稳妥做法是：

1. 只通过 Mac 通达信官方公式管理 UI 录入、修改和删除公式。
2. 保留 `formulas/*.tdx` 作为源码备份。
3. 后续把图形信号和历史 K 线样本对应起来，再决定是否转写为可批量回测的 Python/量化版本。

## 5. 下一步建议

下一步测试重点：

1. 在样本股票上实际切换到 `XHMAIN`、`XHSUB`、`XHWATER`，确认图形能正常渲染。
2. 选取 300660、002916、300308 等样本，记录最近 6-12 个月的买/卖/止盈图标出现日期。
3. 对比每次信号后的最大回撤、后续 5/10/20 日收益、是否滞后、是否过密。
4. 特别检查 `XHWATER` 的数值尺度，因为它使用 `EXP` 和 `POW`，存在极端价格下图形失真的可能。
5. 如果 UI 验证有效，再把公式逻辑拆解为 Python 因子，进入批量回测阶段。
