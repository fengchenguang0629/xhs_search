---
name: xhs-notes-search
description: 从小红书搜索笔记数据并生成摘要。智能图片处理：仅对正文过短的笔记提取图片信息。调用搜索API获取笔记数据，对内容进行智能总结，保留原始笔记链接和引用。使用场景：用户请求搜索小红书内容、查找小红书笔记、搜索小红书话题等。
---

# 小红书笔记搜索与摘要

## 快速开始

### 使用示例

用户输入搜索需求时：

```
从小红书搜索"产后修复"的相关笔记并总结
```

### 处理流程

此技能使用以下工作流程：

1. **搜索阶段**：调用本地Flask API搜索小红书笔记
2. **智能判断**：分析每条笔记正文长度（排除话题标签）
3. **按需提取图片**：仅对正文过短的笔记下载图片并转Base64
4. **模型处理**：当前模型处理图片分析和摘要生成

## 核心特性

### 智能图片处理

**核心优化**：不再对所有笔记下载图片，而是智能判断：

| 内容长度 | 处理方式 |
|---------|---------|
| 正文 ≥ 100字符 | 不提取图片（内容已充足） |
| 正文 < 100字符 | 提取图片信息（主要内容在图片中） |

**优势**：
- 大幅减少不必要的图片下载
- 降低Token消耗（平均减少60%+）
- 提高处理效率

### 无三方客户端

- **不依赖Anthropic SDK**：直接使用调用技能的模型能力
- **图片Vision处理**：由当前模型的Vision API完成
- **灵活适配**：支持任何兼容的LLM（Claude、GPT等）

### 分批图片处理

- 每批处理5张图片，防止单次请求Token过多
- 自动过滤无用图片（返回"无用"的内容）
- 融合多张图片的有用信息

### 标准化输出格式

- **自然语言总结**：清晰易读的Markdown格式
- **上标引用**：使用 `[1]`、`[2]` 标记笔记来源
- **参考资料**：文末附加紧凑的链接列表

## 工作流程详解

### 步骤1：调用搜索API

调用搜索API获取笔记数据（先不处理图片）：

```
from xhs_notes_search.scripts.summarizer import search_and_prepare

data = search_and_prepare(
    query="产后修复",
    require_num=10,
    analyze_images=True,
    content_threshold=100  # 内容长度阈值
)
```

### 步骤2：智能内容分析

自动分析每条笔记：
- 移除话题标签（如 `#产后修复[话题]#`）
- 计算纯净正文长度
- 与阈值比较判断是否需要图片分析

### 步骤3：按需图片处理

仅对需要的笔记：
- 下载图片并转为Base64
- 分批组织（每批5张）
- 生成图片分析任务

返回的数据结构：
```json
{
  "status": "success",
  "query": "搜索词",
  "notes": [
    {
      "index": 1,
      "title": "笔记标题",
      "content": "笔记内容...",
      "content_length": 150,
      "need_image_analysis": false,
      "url": "https://...",
      "images": [],
      "image_urls": ["http://..."]
    }
  ],
  "image_analysis_tasks": [...],
  "statistics": {
    "total_notes": 10,
    "notes_with_sufficient_content": 8,
    "notes_need_image_analysis": 2,
    "image_tasks_created": 2
  },
  "prompt_template": "..."
}
```

### 步骤4：模型处理

对每个 `image_analysis_tasks` 项，使用Vision API分析图片。

## 配置参数

### search_and_prepare() 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | str | 必需 | 搜索关键词 |
| require_num | int | 10 | 返回笔记数量 |
| analyze_images | bool | True | 是否启用智能图片处理 |
| content_threshold | int | 100 | 内容长度阈值（字符） |
| api_url | str | localhost:5000 | Flask API地址 |

### 高级选项

调整阈值以适应不同场景：

```python
# 深度分析：降低阈值，更多笔记会提取图片
search_and_prepare(query="xxx", content_threshold=50)

# 快速模式：提高阈值，减少图片处理
search_and_prepare(query="xxx", content_threshold=200)

# 禁用图片处理
search_and_prepare(query="xxx", analyze_images=False)
```

## 输出格式示例

```markdown
根据小红书笔记，产后修复应该关注以下几点[1]：

- **盆底肌修复**：产后42天检查评估[2]
- **腹直肌修复**：分离2指以上需干预[3]
- **修复顺序**：先腹式呼吸，再腹直肌训练[4]

## 参考资料

[1] [花了4w+的产康经验总结](https://www.xiaohongshu.com/...)
[2] [产康做完了，我来说实话](https://www.xiaohongshu.com/...)
[3] [38岁辣妈产后恢复少女腰](https://www.xiaohongshu.com/...)
[4] [三年生俩0成本恢复身材](https://www.xiaohongshu.com/...)
```

## 技术细节

### 内容清理规则

计算内容长度时会自动排除：
- 话题标签：`#xxx[话题]#` 或 `#xxx#`
- 多余空白字符

### 图片处理流程

1. **判断**：根据内容长度决定是否需要
2. **下载**：仅对需要的笔记下载图片
3. **编码**：转换为Base64格式
4. **分批**：每批5张，避免请求过大
5. **过滤**：模型标记"无用"的图片被排除

### 错误处理

- 搜索API不可用：返回 `{'status': 'error', 'message': '...'}`
- 无结果：返回 `{'status': 'no_results', 'message': '...'}`
- 图片下载失败：保留原始URL链接

## 常见用法

### 基础搜索
```
搜索小红书关于"新生儿护理"的笔记
```

### 指定数量
```
从小红书找10条关于"产后抑郁症"的相关笔记并总结
```

### 深度分析
```
深度搜索小红书关于"宝宝辅食"的内容，要求详细总结
```

## 依赖要求

- Python 3.8+
- requests（用于HTTP请求）
- 本地Flask API服务运行中
- 调用技能的模型支持Vision API（用于图片分析）

## 故障排除

### API连接失败
检查本地Flask服务是否运行：
```bash
python web/app.py
```

### 图片分析效果差
- 确保模型支持Vision API
- 检查 `content_threshold` 设置是否合理
- 图片内容清晰且相关

### Token消耗过多
- 检查是否启用了智能图片处理（`analyze_images=True`）
- 适当提高 `content_threshold` 阈值
- 减少 `require_num` 参数
