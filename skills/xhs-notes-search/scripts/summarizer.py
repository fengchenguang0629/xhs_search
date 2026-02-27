#!/usr/bin/env python3
"""
小红书搜索与总结集成器

调用 /api/notes/search-with-extract 接口，该接口已在服务端完成：
- 图片压缩 + base64 转换
- OCR 文字提取（仅对正文 ≤ 200字 的笔记）

本模块职责：
1. 调用接口获取结构化笔记数据
2. 根据 image_extracted 标识和 images 文字，构建完整的总结提示词
3. 返回供调用模型直接生成总结的上下文
"""

from typing import Dict, List, Optional

try:
    from .api_client import XHSSearchClient
except ImportError:
    from api_client import XHSSearchClient


class XHSSearchSummarizer:
    """小红书搜索与总结集成器"""

    def __init__(self, api_url: str = "http://localhost:5000"):
        """
        初始化

        Args:
            api_url: 搜索API服务地址
        """
        self.api_url = api_url
        self.client = XHSSearchClient(base_url=api_url)

    def search_and_prepare(
        self,
        query: str,
        require_num: int = 10,
    ) -> Dict:
        """
        搜索笔记并准备供模型总结的数据

        接口已处理：
        - 正文 > 200字 → image_extracted=false，images=[]
        - 正文 ≤ 200字 → image_extracted=true，images=[OCR提取的文字行...]

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量

        Returns:
            {
                'status': 'success',
                'query': '...',
                'notes': [...],           # 结构化笔记列表（含 image_extracted 标识）
                'statistics': {...},
                'prompt_template': '...'  # 供模型直接使用的总结提示词
            }
        """
        result = self.client.search(query, require_num=require_num)

        if result.get("status") != "success":
            return {
                "status": "error",
                "message": f"搜索失败: {result.get('message', '未知错误')}"
            }

        notes: List[Dict] = result.get("data", [])
        if not notes:
            return {
                "status": "no_results",
                "message": f"没有找到关于'{query}'的笔记"
            }

        # 统计信息
        extracted_count = sum(1 for n in notes if n.get("image_extracted"))
        stats = {
            "total_notes": len(notes),
            "notes_with_image_extracted": extracted_count,
            "notes_with_sufficient_content": len(notes) - extracted_count,
        }

        print(f"[信息] 笔记统计: 共 {stats['total_notes']} 篇，"
              f"图片已提取文字 {stats['notes_with_image_extracted']} 篇，"
              f"正文充足 {stats['notes_with_sufficient_content']} 篇")

        return {
            "status": "success",
            "query": query,
            "notes": notes,
            "statistics": stats,
            "notes_text": self._build_notes_text(notes)
        }

    def _build_notes_text(self, notes: List[Dict]) -> str:
        """
        将笔记列表拼接为纯文本，供 AI 读取后生成总结。
        总结格式规范见 SKILL.md，不在此处硬编码。

        对每篇笔记：
        - image_extracted=false：使用 content 正文
        - image_extracted=true ：使用 content + images（OCR文字）

        Args:
            notes: 接口返回的笔记列表

        Returns:
            笔记内容文本
        """
        parts: List[str] = []

        for i, note in enumerate(notes, 1):
            title   = note.get("title", f"笔记{i}")
            content = note.get("content", "")
            url     = note.get("url", "")
            images  = note.get("images", [])
            image_extracted = note.get("image_extracted", False)

            content_section = content.strip() if content.strip() else "（正文为空）"

            if image_extracted and images:
                ocr_text = "\n".join(images)
                content_section = (
                    f"{content_section}\n\n【图片提取信息】\n{ocr_text}"
                ).strip()
                heading = f"[笔记{i}] {title}（含图片提取信息）"
            else:
                heading = f"[笔记{i}] {title}"

            parts.append(f"{heading}\n\n{content_section}\n\n链接：{url}")

        return "\n\n---\n\n".join(parts)


def search_and_prepare(
    query: str,
    require_num: int = 10,
    api_url: str = "http://localhost:5000",
    # 以下参数仅保留以兼容旧调用，不再使用
    analyze_images: bool = True,
    content_threshold: Optional[int] = None,
) -> Dict:
    """
    快捷函数：搜索并准备小红书笔记数据

    图片处理由服务端 /api/notes/search-with-extract 完成，
    本函数无需（也不应）在客户端重复处理。

    Args:
        query: 搜索关键词
        require_num: 返回笔记数量
        api_url: API服务地址
        analyze_images: 已废弃，保留仅为兼容旧签名
        content_threshold: 已废弃，保留仅为兼容旧签名

    Returns:
        格式化的数据字典（包含 notes、statistics、notes_text）
    """
    summarizer = XHSSearchSummarizer(api_url=api_url)
    return summarizer.search_and_prepare(query, require_num)


if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "产后修复"
    num   = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    result = search_and_prepare(query=query, require_num=num)
    status = result.get("status")

    if status != "success":
        print(result.get("message", "搜索失败"))
        sys.exit(1)

    # 只输出笔记内容文本，总结格式规范由 AI 根据 SKILL.md 自行应用
    print(result.get("notes_text", ""))
