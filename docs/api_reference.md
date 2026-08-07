# API 参考：归因

## `GET /api/attribution`

查询窗口内订单的规则型归因结果。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `start_time` | 是 | 带时区 ISO 8601 开始时间 |
| `end_time` | 是 | 带时区 ISO 8601 结束时间，使用左闭右开窗口 |
| `model` | 否 | `first_touch`、`last_touch` 或 `linear`；默认 `last_touch` |
| `channel` | 否 | 仅保留匹配的触点，其他订单贡献归入 `unknown` |
| `campaign_id` | 否 | 仅保留匹配的触点，其他订单贡献归入 `unknown` |

响应包含总订单/GMV、已归因与 unknown 贡献、渠道和活动贡献、订单触点路径样例以及数据质量提示。金额、订单贡献和比例均为 JSON 数字；比例范围是 `0~1`。

`422` 表示无效模型、时间窗口或参数；`503` 表示数据库不可用。
