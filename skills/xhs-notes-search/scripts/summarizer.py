#!/usr/bin/env python3
"""
小红书搜索与数据提取集成器
提供搜索、图片处理和数据结构化
不包含LLM总结逻辑（由调用模型处理）

智能图片处理策略：
- 正文内容充足（>content_threshold字符）→ 不提取图片
- 正文内容过短 → 提取图片信息
"""

import re
from typing import Dict, List, Optional, Tuple

# 支持多种导入方式
try:
    from .api_client import XHSSearchClient
    from .image_processor import ImageProcessor
except ImportError:
    try:
        from api_client import XHSSearchClient
        from image_processor import ImageProcessor
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from api_client import XHSSearchClient
        from image_processor import ImageProcessor


class XHSSearchSummarizer:
    """小红书搜索与数据提取集成器"""

    # 默认内容长度阈值（字符数，不含话题标签）
    DEFAULT_CONTENT_THRESHOLD = 100

    def __init__(self, api_url: str = "http://localhost:5000"):
        """
        初始化检索器

        Args:
            api_url: 搜索API服务地址
        """
        self.api_url = api_url
        self.client = XHSSearchClient(base_url=api_url)
        self.image_processor = ImageProcessor()

    def _clean_content(self, content: str) -> str:
        """
        清理内容，移除话题标签，返回纯净文本

        Args:
            content: 原始内容

        Returns:
            清理后的内容
        """
        # 移除话题标签 #xxx[话题]# 或 #xxx#
        cleaned = re.sub(r'#[^#\[]+(\[话题\])?#?', '', content)
        # 移除多余空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _should_extract_images(
        self,
        content: str,
        threshold: int
    ) -> Tuple[bool, int]:
        """
        判断是否需要提取图片信息

        Args:
            content: 笔记正文内容
            threshold: 内容长度阈值

        Returns:
            (是否需要提取图片, 清理后内容长度)
        """
        clean_content = self._clean_content(content)
        content_length = len(clean_content)
        return content_length < threshold, content_length

    def search_and_prepare(
        self,
        query: str,
        require_num: int = 10,
        analyze_images: bool = True,
        content_threshold: Optional[int] = None
    ) -> Dict:
        """
        搜索笔记并准备数据供模型处理

        智能图片处理策略：
        - analyze_images=True 时启用智能判断
        - 正文内容 > threshold → 不提取图片
        - 正文内容 < threshold → 提取图片

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            analyze_images: 是否启用智能图片处理
            content_threshold: 内容长度阈值，默认100字符

        Returns:
            包含笔记、图片分析任务的字典
        """
        if content_threshold is None:
            content_threshold = self.DEFAULT_CONTENT_THRESHOLD

        print(f"[信息] 开始搜索: {query}")

        # 步骤1: 先搜索，不处理图片（获取原始数据）
        result = self.client.search(
            query,
            require_num=require_num,
            process_images=False  # 先不处理图片
        )

        if result['status'] != 'success':
            return {
                'status': 'error',
                'message': f"搜索失败: {result.get('message', '未知错误')}"
            }

        notes = result['data']
        if not notes:
            return {
                'status': 'no_results',
                'message': f"没有找到关于'{query}'的笔记"
            }

        print(f"[信息] 获得 {len(notes)} 条笔记")

        # 步骤2: 分析每条笔记，判断是否需要提取图片
        notes_need_images = []  # 需要提取图片的笔记索引
        content_analysis = []   # 内容分析结果

        for i, note in enumerate(notes):
            content = note.get('content', '')
            need_images, content_len = self._should_extract_images(
                content, content_threshold
            )
            content_analysis.append({
                'index': i,
                'content_length': content_len,
                'need_images': need_images
            })
            if need_images and analyze_images and note.get('images'):
                notes_need_images.append(i)

        print(f"[信息] 内容分析完成:")
        print(f"  - 内容充足的笔记: {len(notes) - len(notes_need_images)} 条")
        print(f"  - 需要提取图片的笔记: {len(notes_need_images)} 条")

        # 步骤3: 只对需要的笔记处理图片
        if notes_need_images and analyze_images:
            print(f"[信息] 开始处理 {len(notes_need_images)} 条笔记的图片...")
            for idx in notes_need_images:
                note = notes[idx]
                if note.get('images'):
                    note['processed_images'] = self.image_processor.process_images_in_note(
                        {'images': note['images']}
                    ).get('processed_images', [])

        # 步骤4: 结构化笔记数据
        notes_data = []
        image_tasks = []

        for i, note in enumerate(notes, 1):
            # 添加图片分析标记
            analysis = content_analysis[i-1]
            note_info = {
                "index": i,
                "title": note.get('title', f'笔记{i}'),
                "content": note.get('content', ''),
                "content_length": analysis['content_length'],
                "need_image_analysis": analysis['need_images'],
                "url": note.get('url', ''),
                "images": note.get('processed_images', []),
                "image_urls": note.get('images', [])  # 保留原始图片URL
            }
            notes_data.append(note_info)

            # 步骤5: 只为需要图片分析的笔记生成任务
            if analyze_images and analysis['need_images'] and note_info['images']:
                task = self._build_image_analysis_task(i, note_info)
                if task:
                    image_tasks.append(task)

        print(f"[信息] 准备了 {len(image_tasks)} 个图片分析任务")

        return {
            'status': 'success',
            'query': query,
            'notes': notes_data,
            'image_analysis_tasks': image_tasks,
            'content_threshold': content_threshold,
            'statistics': {
                'total_notes': len(notes),
                'notes_with_sufficient_content': len(notes) - len(notes_need_images),
                'notes_need_image_analysis': len(notes_need_images),
                'image_tasks_created': len(image_tasks)
            },
            'prompt_template': self._build_summarize_prompt_template(notes_data)
        }

    def _build_image_analysis_task(
        self,
        note_index: int,
        note_info: Dict
    ) -> Optional[Dict]:
        """
        构建图片分析任务（由模型执行）

        Args:
            note_index: 笔记索引
            note_info: 笔记信息

        Returns:
            图片分析任务数据
        """
        images = note_info.get('images', [])
        if not images:
            return None

        content = note_info.get('content', '')
        batch_size = 5  # 每批处理5张图片

        batches = []
        for batch_start in range(0, len(images), batch_size):
            batch_end = min(batch_start + batch_size, len(images))
            batch_images = images[batch_start:batch_end]

            batch_data = {
                "images": [
                    {
                        "base64": img.get('base64'),
                        "media_type": img.get('media_type', 'image/webp'),
                        "url": img.get('url')
                    }
                    for img in batch_images
                    if img.get('base64')
                ]
            }

            if batch_data['images']:
                batches.append(batch_data)

        if not batches:
            return None

        return {
            "note_index": note_index,
            "note_title": note_info.get('title'),
            "note_content_length": note_info.get('content_length', 0),
            "note_content_snippet": content[:300],
            "batches": batches,
            "prompt": f"请简洁地提取这些图片中的关键信息。相关笔记内容：{content[:300]}\n\n请只返回有用的信息，如果图片无用请返回'无用'。"
        }

    def _build_summarize_prompt_template(self, notes_data: List[Dict]) -> str:
        """
        构建总结提示词模板（模型填充图片分析后的内容）

        Args:
            notes_data: 笔记列表

        Returns:
            提示词模板
        """
        notes_context = []
        for note in notes_data:
            img_status = "需图片分析" if note.get('need_image_analysis') else "内容充足"
            part = f"[笔记{note['index']}] {note['title']} ({img_status})\n\n内容：{note['content']}\n\n链接：{note['url']}"
            notes_context.append(part)

        notes_text = "\n\n---\n\n".join(notes_context)

        prompt = f"""请根据以下小红书笔记内容（包括文字内容和图片分析信息），生成一份清晰、简洁的总结。

笔记信息：
{notes_text}

##要求：
1. 总结内容应该是自然语言描述
2. 使用Markdown上标引用格式标记笔记来源，如[1]、[2]等
3. 文末附加紧凑的参考资料列表，格式为"[编号] [标题](链接)"
4. 不需要包含"# 标题"这样的主标题
5. 内容简洁有力，避免冗长

请提供总结："""

        return prompt

    def search_and_summarize(
        self,
        query: str,
        require_num: int = 10,
        analyze_images: bool = True,
        content_threshold: Optional[int] = None
    ) -> Dict:
        """
        搜索笔记并返回完整数据（向后兼容）

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            analyze_images: 是否分析图片内容
            content_threshold: 内容长度阈值

        Returns:
            准备好的数据字典
        """
        return self.search_and_prepare(query, require_num, analyze_images, content_threshold)


def search_and_prepare(
    query: str,
    require_num: int = 10,
    analyze_images: bool = True,
    content_threshold: Optional[int] = None,
    api_url: str = "http://localhost:5000"
) -> Dict:
    """
    快捷函数：搜索并准备小红书笔记数据

    智能图片处理策略：
    - analyze_images=True 时启用智能判断
    - 正文内容 > threshold → 不提取图片
    - 正文内容 < threshold → 提取图片

    Args:
        query: 搜索关键词
        require_num: 返回笔记数量
        analyze_images: 是否启用智能图片处理
        content_threshold: 内容长度阈值（默认100字符）
        api_url: API服务地址

    Returns:
        格式化的数据字典（包含笔记、图片任务、提示词）
    """
    summarizer = XHSSearchSummarizer(api_url=api_url)
    return summarizer.search_and_prepare(query, require_num, analyze_images, content_threshold)


if __name__ == "__main__":
    print("=" * 60)
    print("小红书搜索与数据提取（智能图片处理版）")
    print("=" * 60)
    print("\n功能说明:")
    print("1. 先搜索获取笔记原始数据")
    print("2. 分析每条笔记正文长度（排除话题标签）")
    print("3. 内容充足的笔记（>100字符）不提取图片")
    print("4. 内容过短的笔记才下载图片并生成分析任务")
    print("\n优点:")
    print("- 大幅减少不必要的图片下载")
    print("- 降低Token消耗")
    print("- 提高处理效率")
    print("\n示例用法:")
    print("""
# 调用搜索API（智能模式）
search_result = search_and_prepare(
    query="产后修复",
    require_num=10,
    analyze_images=True,  # 启用智能图片处理
    content_threshold=100  # 内容阈值，可调整
)

# 返回结果包含：
# - search_result['notes']：笔记列表
# - search_result['image_analysis_tasks']：图片分析任务（仅内容过短的笔记）
# - search_result['statistics']：处理统计信息
# - search_result['prompt_template']：总结提示词模板
    """)
