#!/usr/bin/env python3
"""
小红书搜索与数据提取集成器
提供搜索、图片处理和数据结构化
不包含LLM总结逻辑（由调用模型处理）
"""

from typing import Dict, List, Optional

# 支持多种导入方式
try:
    from .api_client import search_xhs_notes
except ImportError:
    try:
        from api_client import search_xhs_notes
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from api_client import search_xhs_notes


class XHSSearchSummarizer:
    """小红书搜索与数据提取集成器"""

    def __init__(self, api_url: str = "http://localhost:5000"):
        """
        初始化检索器

        Args:
            api_url: 搜索API服务地址
        """
        self.api_url = api_url

    def search_and_prepare(
        self,
        query: str,
        require_num: int = 10,
        analyze_images: bool = True
    ) -> Dict:
        """
        搜索笔记并准备数据供模型处理

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            analyze_images: 是否包含图片信息

        Returns:
            包含笔记、图片分析任务的字典
        """
        print(f"[信息] 开始搜索: {query}")

        # 步骤1: 搜索并处理图片
        result = search_xhs_notes(
            query,
            require_num=require_num,
            process_images=analyze_images,
            api_url=self.api_url
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

        # 步骤2: 结构化笔记数据
        notes_data = []
        image_tasks = []

        for i, note in enumerate(notes, 1):
            note_info = {
                "index": i,
                "title": note.get('title', f'笔记{i}'),
                "content": note.get('content', ''),
                "url": note.get('url', ''),
                "images": note.get('processed_images', [])
            }
            notes_data.append(note_info)

            # 步骤3: 为有图片的笔记生成图片分析任务
            if analyze_images and note_info['images']:
                task = self._build_image_analysis_task(i, note_info)
                if task:
                    image_tasks.append(task)

        print(f"[信息] 准备了 {len(image_tasks)} 个图片分析任务")

        return {
            'status': 'success',
            'query': query,
            'notes': notes_data,
            'image_analysis_tasks': image_tasks,
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
            part = f"[笔记{note['index']}] {note['title']}\n\n内容：{note['content']}\n\n链接：{note['url']}"
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
        analyze_images: bool = True
    ) -> Dict:
        """
        搜索笔记并返回完整数据（向后兼容）

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            analyze_images: 是否分析图片内容

        Returns:
            准备好的数据字典
        """
        return self.search_and_prepare(query, require_num, analyze_images)


def search_and_prepare(
    query: str,
    require_num: int = 10,
    analyze_images: bool = True,
    api_url: str = "http://localhost:5000"
) -> Dict:
    """
    快捷函数：搜索并准备小红书笔记数据

    Args:
        query: 搜索关键词
        require_num: 返回笔记数量
        analyze_images: 是否包含图片分析任务
        api_url: API服务地址

    Returns:
        格式化的数据字典（包含笔记、图片任务、提示词）
    """
    summarizer = XHSSearchSummarizer(api_url=api_url)
    return summarizer.search_and_prepare(query, require_num, analyze_images)


if __name__ == "__main__":
    print("=" * 60)
    print("小红书搜索与数据提取")
    print("=" * 60)
    print("\n⚠️  使用说明:")
    print("此模块为技能提供搜索和数据准备功能")
    print("在CatPaw技能中调用时，模型将处理图片分析和总结生成\n")
    print("示例用法（在CatPaw技能中）:")
    print("""
# 调用搜索API
search_result = search_and_prepare(
    query="二月龄小宝宝喂养",
    require_num=10,
    analyze_images=True
)

# 模型将获得：
# - search_result['notes']：笔记列表
# - search_result['image_analysis_tasks']：图片分析任务
# - search_result['prompt_template']：总结提示词模板

# 模型执行图片分析任务，然后生成总结
    """)

