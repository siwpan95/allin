# 纯黑缩略图根因分析报告

## 概述

- **总缩略图数**: 8886
- **纯黑缩略图数**: 2126 (23.9%)
- **正常缩略图数**: 6760 (76.1%)

## 根因分类

### 1. COLOR_USES_UNDEFINED_PARAMS (约 35%，〜745 个)

**描述**: 颜色公式使用了参数（如 `a1`, `b1`, `f1`, `p1`, `w1` 等），但这些参数可能未定义或默认为 0，导致颜色输出为 0。

**典型示例**:
```json
{
  "color": {
    "red": "clip(a1 + b1*v, 0, 1)",
    "green": "clip(a2 + b2*v, 0, 1)",
    "blue": "clip(a3 + b3*v, 0, 1)"
  }
```
如果 `a1=a2=a3=0` 且 `b1=b2=b3=0`，颜色输出恒为 0。

**另一示例**:
```json
{
  "color": {
    "red": "clip(v*f1 + p1 if v < w1 else (v-1)*f2 + p2, 0, 1)",
    "green": "clip(v*f3 + p3 if v < w1 else (v-1)*f4 + p4, 0, 1)",
    "blue": "clip(v*f5 + p5 if v < w1 else (v-1)*f6 + p6, 0, 1)"
  }
```
如果所有参数 `f1-f6`, `p1-p6` 都为 0，颜色输出恒为 0。

**修复建议**:
1. 检查渲染器中这些参数的默认值
2. 为使用参数的颜色方案提供合理的默认参数值
3. 或者修改颜色方案，避免使用未定义参数

---

### 2. COLOR_MAY_PRODUCE_ZERO (约 41%，〜870 个)

**描述**: 颜色公式可能产生 0 或接近 0 的值，导致图片非常暗或纯黑。

**典型模式**:
- `0.25*int(v*4)` - 当 v 较小时输出 0
- `v*f1` - 如果 f1 较小或为 0，输出接近 0

**修复建议**:
1. 检查颜色公式是否能产生足够宽的数值范围
2. 对于可能产生暗色的公式，考虑添加亮度增益

---

### 3. CYCLE_NO_STEPS (199 个, 9.4%)

**描述**: `cycle.steps <= 0`，没有执行任何演化步骤，网格保持初始状态（可能为全0）。

**典型示例**:
```json
{
  "cycle": {
    "steps": 0
  }
}
```

**修复建议**: 将 `cycle.steps` 设置为正整数（建议 50-500）。

---

### 4. COLOR_CATEGORICAL8_BUG (165 个, 7.8%)

**描述**: 使用 `Categorical8` 颜色方案的所有缩略图都是纯黑的。

**预期行为**: 即使 `v=0`，`Categorical8` 应产生 `(0, 0.5, 1)` 而不是黑色。

**实际行为**: 所有使用 `Categorical8` 的缩略图都是纯黑（RGB 0,0,0）。

**疑似原因**: 渲染器对 `Categorical8` 公式的实现有 bug。

**Categorical8 公式**:
```json
{
  "red": "clip(int(v*8)/8, 0, 1)",
  "green": "clip(int(v*8 + 4)/8 % 1, 0, 1)",
  "blue": "clip(1 - int(v*8)/8, 0, 1)"
}
```

**修复建议**:
1. 检查渲染器中 `Categorical8` 颜色公式的实现
2. 临时解决方案：将 `Categorical8` 替换为 `Grayscale` 或 `SinePalette`

---

### 5. BINARY_SOLARIZE_ISSUE (73 个, 3.4%)

**描述**: `Solarize` 颜色方案与二进制演化规则不兼容。

**问题**:
- `Solarize` 公式: `"1-v if v > 0.5 else v"`
- 二进制规则输出 `v=0` 或 `v=1`
- 当 `v=0`: color = 0
- 当 `v=1`: color = 1-1 = 0
- **所有单元格的颜色都是 0 → 纯黑！**

**典型示例**:
```json
{
  "evolution": {
    "rule": "1 if (sum_n >= 1 and sum_n <= 5) else 0"
  },
  "color": {
    "red": "1-v if v > 0.5 else v",
    "green": "1-v if v > 0.5 else v",
    "blue": "1-v if v > 0.5 else v"
  }
}
```

**修复建议**: 将 `Solarize` 颜色方案改为 `Categorical8`、`Grayscale` 或 `SinePalette`。

---

### 6. LIFELIKE_T6 (57 个, 2.7%)

**描述**: Life-like 演化规则阈值 `>=6` 过高，导致图案消失（所有细胞死亡）。

**典型规则**: `"1 if sum_n >= 6 else 0"`

**问题**: 需要 6 个或更多邻居才能存活/出生，对于大多数初始图案来说阈值过高，导致图案快速消失。

**修复建议**: 降低阈值（如改为 `T2,3,3`）或改用其他规则。

---

## 修复优先级

| 优先级 | 根因 | 数量 | 修复难度 |
|--------|------|------|----------|
| HIGH | CYCLE_NO_STEPS | 199 | 简单 |
| HIGH | COLOR_CATEGORICAL8_BUG | 165 | 中等（需修复渲染器） |
| HIGH | BINARY_SOLARIZE_ISSUE | 73 | 简单 |
| MEDIUM | COLOR_USES_UNDEFINED_PARAMS | 〜745 | 中等 |
| MEDIUM | LIFELIKE_T6 | 57 | 简单 |
| LOW | COLOR_MAY_PRODUCE_ZERO | 〜870 | 复杂 |

## 下一步行动

1. **立即修复** (CYCLE_NO_STEPS): 批量将 `steps <= 0` 的文件修复
2. **检查渲染器** (COLOR_CATEGORICAL8_BUG): 检查 `Categorical8` 实现
3. **批量替换** (BINARY_SOLARIZE_ISSUE): 将 `Solarize` + 二进制规则的组合改为其他颜色方案
4. **参数默认值**: 为颜色公式中的参数提供合理的默认值
5. **深入调查**: 对于剩余未知案例，需要实际模拟演化或检查渲染器代码

## 附录：完整统计数据

- 总黑图数: 2126
- 已识别根因: 〜1409 (66.2%)
- 未识别根因: 〜717 (33.8%)

**注意**: 某些黑图可能有多个根因（如同时使用 `Categorical8` 和 `steps>0`），上述统计可能有重叠。
