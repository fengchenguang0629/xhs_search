---
name: xhs-notes-search
description: 从小红书搜索笔记数据并生成摘要。调用 /api/notes/search-with-extract 接口，服务端已完成图片压缩、base64转换和OCR提取，根据正文长度自动判断是否进行图片文字提取，image_extracted 标识图片是否已提取，images 字段为提取的图片文字行。脚本只负责输出笔记纯文本内容，AI 按照本文档「总结规范」章节的格式要求生成总结，保留原始笔记链接和引用。使用场景：用户请求搜索小红书内容、查找小红书笔记、搜索小红书话题等。
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

1. **搜索**：运行 `summarizer.py <关键词>`，调用 `/api/notes/search-with-extract` 获取笔记
2. **服务端智能处理**（自动完成）：
   - 正文 > 200字：内容充足，`images=[]`，`image_extracted=false`
   - 正文 ≤ 200字：对图片OCR提取，`images=[文字行...]`，`image_extracted=true`
3. **输出**：脚本打印所有笔记的纯文本内容（标题、正文、OCR文字、链接）
4. **总结**：AI 按照本文档"总结规范"部分的要求，对脚本输出的笔记内容生成总结

## 接口返回数据格式

`/api/notes/search-with-extract` 返回的每条笔记结构：

```json
{
    "id":              "笔记ID",
    "url":             "笔记URL",
    "title":           "标题",
    "content":         "正文",
    "images":          ["OCR提取的文字行1", "文字行2"],
    "liked_count":     "123",
    "comment_count":   "45",
    "share_count":     "6",
    "image_extracted": true
}
```

| 字段 | 说明 |
|------|------|
| `image_extracted` | `true`=已对图片进行OCR提取，`false`=正文充足或无图片 |
| `images` | `image_extracted=true` 时为OCR提取的文字行列表；`false` 时为空列表 |
| `content` | 原始正文 |

## 核心特性

### 服务端智能图片处理

**图片处理由服务端 `/api/notes/search-with-extract` 完成**，客户端无需处理：

| 内容长度 | 处理方式 |
|---------|---------|
| 正文 > 200字 | 不提取图片（内容已充足），`image_extracted=false` |
| 正文 ≤ 200字 | 图片OCR提取，`image_extracted=true`，`images` 为文字行 |

**优势**：
- 不依赖客户端Vision API
- 服务端统一压缩（1024px，quality=85），OCR效果有保障
- 客户端只需处理纯文本数据，适配任何LLM

### 无三方客户端

- **不依赖Anthropic SDK**：直接使用调用技能的模型能力
- **图片已转文字**：OCR结果以文字行列表形式返回，普通文本处理即可
- **灵活适配**：支持任何兼容的LLM（Claude、GPT等）

### 标准化输出格式

- **自然语言总结**：清晰易读的Markdown格式
- **上标引用**：使用 `[1]`、`[2]` 标记笔记来源
- **参考资料**：文末附加紧凑的链接列表

## 工作流程详解

### 步骤1：调用搜索API

```python
from skills.xhs_notes_search.scripts.summarizer import search_and_prepare

data = search_and_prepare(
    query="产后修复",
    require_num=10,
    api_url="http://localhost:5000"
)
```

### 步骤2：读取返回数据

```python
notes = data['notes']   # 笔记列表
for note in notes:
    print(note['title'])
    print(note['image_extracted'])   # True/False
    print(note['images'])            # OCR文字行列表（或空列表）
```

### 步骤3：读取笔记文本

```python
notes_text = data['notes_text']
# 笔记文本包含：标题、正文（含图片OCR文字）、链接
# AI 按照 SKILL.md「总结规范」对此文本生成总结
```

返回的数据结构：

```json
{
  "status": "success",
  "query": "搜索词",
  "notes": [
    {
      "id":              "...",
      "url":             "https://...",
      "title":           "笔记标题",
      "content":         "正文内容...",
      "images":          ["提取的文字行"],
      "liked_count":     "100",
      "comment_count":   "20",
      "share_count":     "5",
      "image_extracted": true
    }
  ],
  "statistics": {
    "total_notes": 10,
    "notes_with_image_extracted": 3,
    "notes_with_sufficient_content": 7
  },
  "notes_text": "[笔记1] 标题\n\n正文...\n\n链接：https://..."
}
```

### 步骤4：按总结规范生成总结

读取 `notes_text`，严格按照本文档「总结规范」章节的格式要求，由 AI 生成 Markdown 格式总结。

## 总结规范

脚本输出笔记内容后，AI 必须严格按照以下规范生成总结。

### 格式要求

1. **语言**：自然语言描述，使用 Markdown 格式
2. **引用标注**：用上标数字标记笔记来源，如 `[1]`、`[2]`，引用序号对应笔记列表中的编号
3. **结构**：
   - 不加 `# 主标题`（直接从正文开始）
   - 按话题分段，每段用 `##` 小标题
   - 重点内容用加粗或列表呈现
4. **内容要求**：
   - 综合多篇笔记的共同经验和观点
   - 保留关键数字、时间节点、注意事项等具体信息
   - 内容简洁有力，避免冗长和复述
5. **参考资料**：文末附加参考列表，每条格式为 `[编号] [标题](链接)`，紧凑排列不加空行

### 输出格式示例

```markdown
根据多位妈妈的经验，产后修复应优先关注以下几个方面：

## 盆底肌修复
- 产后42天起即可开始评估和训练[1]
- 分娩方式不影响盆底损伤，顺产剖宫产均需重视[2]

## 腹直肌修复
- 先做腹式呼吸激活深层核心肌群，再进行腹直肌训练[3]
- 分离超过2指建议在专业指导下干预[4]

## 参考资料
[1] [花了4w+的产康经验总结](https://www.xiaohongshu.com/...)
[2] [产康做完了，我来说实话](https://www.xiaohongshu.com/...)
[3] [38岁辣妈产后恢复少女腰](https://www.xiaohongshu.com/...)
[4] [三年生俩0成本恢复身材](https://www.xiaohongshu.com/...)
```

## 配置参数

### search_and_prepare() 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | str | 必需 | 搜索关键词 |
| require_num | int | 10 | 返回笔记数量 |
| api_url | str | localhost:5000 | Flask API地址 |

> 注意：图片处理阈值（200字）由服务端控制，客户端无需配置。

## 技术细节

### 服务端图片处理流程

1. **判断**：正文长度（去除话题标签后）与 200 字阈值比较
2. **压缩**：图片缩放至最大 1024px，JPEG quality=85，保障OCR效果
3. **Base64**：转换为 base64 供 LLM Vision API 调用
4. **OCR**：LLM 提取图片中的文字，返回文字行列表
5. **标识**：`image_extracted=true` 表示 `images` 中为文字内容

### 错误处理

- 搜索API不可用：返回 `{'status': 'error', 'message': '...'}`
- 无结果：返回 `{'status': 'no_results', 'message': '...'}`
- 单张图片处理失败：跳过该图片，继续处理其他图片

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
- 本地Flask API服务运行中（`python web/app.py`）

## 故障排除

### API连接失败
检查本地Flask服务是否运行：
```bash
python web/app.py
```

### 图片提取效果差
- 确认图片分辨率是否合理（服务端已优化至1024px）
- 检查图片内容是否清晰可读
- 对于纯图片笔记，OCR效果取决于图片质量

### 请求超时
- 图片OCR处理耗时较长（每张约1-3秒）
- 建议 `timeout` 设置为 120 秒以上
- 减少 `require_num` 可加快响应
