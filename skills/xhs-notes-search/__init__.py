"""
小红书笔记搜索与数据提取技能

调用 /api/notes/search-with-extract 接口：
- 服务端完成图片压缩、base64转换和OCR提取
- 根据正文长度自动判断是否提取图片文字
- 返回结构化数据，客户端直接生成总结
"""

from .scripts.api_client import XHSSearchClient, search_xhs_notes
from .scripts.summarizer import XHSSearchSummarizer, search_and_prepare

__all__ = [
    'XHSSearchClient',
    'search_xhs_notes',
    'XHSSearchSummarizer',
    'search_and_prepare',
]
