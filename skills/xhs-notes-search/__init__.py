"""
小红书笔记搜索与数据提取技能
返回结构化数据供调用模型进行图片分析和摘要生成
"""

from .scripts.api_client import XHSSearchClient, search_xhs_notes
from .scripts.summarizer import XHSSearchSummarizer, search_and_prepare
from extensions.image_processor import ImageProcessor, process_xhs_images, get_image_base64

__all__ = [
    'XHSSearchClient',
    'search_xhs_notes',
    'XHSSearchSummarizer',
    'search_and_prepare',
    'ImageProcessor',
    'process_xhs_images',
    'get_image_base64',
]
