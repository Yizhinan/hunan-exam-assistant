# 上岸难度指数模型 — 考情分析模块完善

日期: 2026-06-29 | 状态: 待实现

---

## 1. 目标

改造考情分析模块的推荐引擎，从「仅按进面分排序」升级为「综合上岸难度评分」，帮助用户找到最容易上岸的岗位。

---

## 2. 难度指数模型

### 2.1 核心公式

```
难度分 = 进面分因子(×0.40) + 竞争比因子(×0.35) + 招录规模因子(×0.15) + 趋势修正因子(×0.10)
```

范围 0-100，越低越容易上岸。

### 2.2 各因子定义

**进面分因子（权重 0.40）**
- 取岗位 min_score_interview
- 同一批次结果内 Min-Max 归一化到 0-100
- 缺数据时用同城市同类别的均分估算

**竞争比因子（权重 0.35）**
- applicant_count / enrollment_count
- Min-Max 归一化到 0-100
- 缺报名数时用同类别均值填充
- 竞争比越低，得分越低（越容易）

**招录规模因子（权重 0.15）**
- 使用 1 / enrollment_count 归一化
- 招录人数越多，上岸概率分母越大

**趋势修正因子（权重 0.10）**
- 比较同一部门同岗位历年进面分变化
- 分数逐年下降 → 正向修正（减分）
- 分数逐年上升 → 负向修正（加分）
- 无历史数据 → 修正值为 0

### 2.3 分层规则

| 档次 | 难度分 | 标签 |
|------|--------|------|
| 保底 | 0-35 | 上岸概率大 |
| 稳妥 | 35-65 | 正常发挥可上岸 |
| 冲刺 | 65-100 | 需要超常发挥 |

---

## 3. 后端改动

### 3.1 新增: 难度计算服务 `backend/app/services/difficulty.py`

提供纯函数:
- `compute_difficulty(position, all_positions, trend_data) -> DifficultyResult`
- `compute_batch_difficulties(positions, trend_map) -> list[tuple[Position, DifficultyResult]]`
- `get_tier(score: float) -> str`

`DifficultyResult` 包含总分和分项得分。

### 3.2 改造: `POST /api/analysis/recommend`

响应中每个 PositionOut 新增字段:
- `difficulty_score: float` — 上岸难度分 (0-100)
- `difficulty_breakdown: object` — 各因子分项
- `tier: str` — 保底/稳妥/冲刺

排序改为按 difficulty_score 升序（最容易的排最前）。

### 3.3 新增: `GET /api/analysis/trend/{city}`

返回指定城市历年进面均分趋势:
```json
{
  "city": "长沙",
  "data": [
    {"year": 2023, "avg_score": 135.2, "count": 25},
    {"year": 2024, "avg_score": 136.8, "count": 30}
  ]
}
```

### 3.4 新增: `GET /api/analysis/stats/overview`

返回全量统计概览:
```json
{
  "by_city": [{"city": "长沙", "avg_score": 136.5, "avg_ratio": 180.2, "count": 30}],
  "by_category": [{"category": "省市直", "avg_score": 138.2, "avg_ratio": 210.5, "count": 45}],
  "easiest_city": "湘西",
  "easiest_category": "县乡基层"
}
```

---

## 4. 前端改动

### 4.1 改造: ResultPage

- 岗位列表按难度分排序
- 顶部新增概览统计卡片（匹配岗位数/平均难度/最容易城市/建议档次分布）
- 结果持久化: 使用 URL search params 存储表单参数，刷新不丢失

### 4.2 改造: PositionCard 组件

- 难度分以环形进度条展示，颜色跟随分层
- 分档标签（保底🟢/稳妥🟡/冲刺🔴）
- 展开查看分项因子明细

### 4.3 新增: TrendChart 组件

- 使用 recharts（已在依赖中）绘制历年趋势折线图
- 支持按城市切换
- 两个指标: 进面均分趋势、竞争比趋势

### 4.4 改造: FormPage

- 提交时保留表单参数到 URL search params
- 结果页刷新时可从 URL 重建请求并重新调用 API

---

## 5. 数据

种子数据已有 56 条岗位（2023-2024），包含进面分和报名数。模型可直接使用。

趋势数据需至少两个年份的同名岗位才能计算——当前种子数据中省直发改委、长沙市政府办等少数岗位有跨年记录，大部分只有 2024 年。趋势修正因子在缺数据时退化为 0，不影响排序可用性。

后续可通过爬虫补充更多年份数据以增强趋势因子的作用。

---

## 6. 路由/文件清单

| 文件 | 操作 |
|------|------|
| `backend/app/services/__init__.py` | 新增 |
| `backend/app/services/difficulty.py` | 新增 — 难度计算 |
| `backend/app/api/analysis.py` | 改造 — recommend 加难度字段、新增 trend + stats |
| `backend/app/main.py` | 不修改（路由无需变） |
| `frontend/src/services/api.ts` | 改造 — 补全类型定义 |
| `frontend/src/pages/Analysis/ResultPage.tsx` | 改造 — 概览卡片 + URL 持久化 |
| `frontend/src/pages/Analysis/FormPage.tsx` | 改造 — URL 参数 |
| `frontend/src/components/analysis/PositionCard.tsx` | 新增 — 可复用卡片 |
| `frontend/src/components/analysis/DifficultyRing.tsx` | 新增 — 难度环形图 |
| `frontend/src/components/analysis/TrendChart.tsx` | 新增 — 趋势折线图 |
| `frontend/src/components/analysis/StatsOverview.tsx` | 新增 — 结果概览 |

---

## 7. 不在范围内

- 不在本次加入行测刷题模块
- 不增加用户之间的横向对比功能
- 不引入新的外部数据源/爬虫任务
- 不修改认证和权限逻辑
