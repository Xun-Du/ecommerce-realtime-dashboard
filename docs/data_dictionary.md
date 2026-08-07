# 数据字典与归因口径

## 事件事实表

`events` 是指标、实验和归因的统一事实表。M5 使用 `click` 作为营销触点，`buy` 作为订单事实；归因主维度为 `channel`，`source`、`medium`、`campaign_id` 和 `campaign_name` 提供营销解释与活动下钻。

每个 `buy` 事件应有唯一 `order_id` 和正数 `order_value`。旧数据缺少 `order_id` 时迁移以 `event_id` 回填；缺少 `source` 时以 `channel` 回填。

## 归因规则

- 订单窗口为 `[start_time, end_time)`，数据库和 API 时间均为 UTC。
- 每笔订单向前回溯 30 天，仅使用同一用户、发生在购买前的 `click`。
- 同一用户、session、渠道和活动的连续点击折叠为一个触点。
- `first_touch` 将全部贡献给最早触点；`last_touch` 给最近触点；`linear` 均分给全部触点。
- 无触点、无渠道或被查询过滤排除的订单计入 `unknown`，因此总 GMV 始终守恒。

归因结果是规则化贡献，而不是营销因果增量。
