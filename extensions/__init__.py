"""
extensions 扩展包
提供模型调用、图片处理等公共工具
"""

from .model_client import analyze_note_relevance
from .image_processor import ImageProcessor, process_xhs_images, get_image_base64

__all__ = [
    'analyze_note_relevance',
    'ImageProcessor',
    'process_xhs_images',
    'get_image_base64',
]
