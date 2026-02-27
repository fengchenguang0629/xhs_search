#!/usr/bin/env python3
"""
OpenAI 兼容模型调用公共方法
从 .env 文件读取以下配置：
  API_KEY    - 模型 API Key
  BASE_URL   - 模型接口地址（OpenAI 兼容）
  MODEL_NAME - 模型名称
"""

import os
import json
from typing import Optional, List, Dict

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

from .image_processor import ImageProcessor

load_dotenv()

_API_KEY: Optional[str] = os.getenv("API_KEY")
_BASE_URL: Optional[str] = os.getenv("BASE_URL")
_MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o-mini")


def _get_client() -> OpenAI:
    """创建 OpenAI 兼容客户端"""
    if not _API_KEY:
        raise ValueError("未设置环境变量 API_KEY，请检查 .env 文件")
    return OpenAI(api_key=_API_KEY, base_url=_BASE_URL)


def analyze_images_relevance(
    title: str,
    image_urls: List[str],
    max_images: int = 3
) -> Dict:
    """
    专门分析图片与标题的相关性，并提取图片中的文字信息
    
    Args:
        title: 笔记标题
        image_urls: 图片URL列表
        max_images: 最多处理的图片数量
        
    Returns:
        {
            "relevant": bool,           # 图片是否与标题相关
            "extracted_text": str|None, # 提取的文字信息
            "reason": str,              # 判断理由
            "processed_images": int     # 实际处理的图片数量
        }
    """
    if not image_urls:
        return {
            "relevant": False,
            "extracted_text": None,
            "reason": "没有提供图片",
            "processed_images": 0
        }
    
    client = _get_client()
    image_processor = ImageProcessor(max_images_per_note=max_images)
    
    # 限制处理的图片数量
    image_urls = image_urls[:max_images]
    
    # 系统提示词 - 专门针对图片分析
    system_prompt = (
        "你是一个专业的图片内容分析助手，擅长：\n"
        "1. 判断图片内容是否与给定标题相关\n"
        "2. 从图片中提取文字信息（OCR）\n"
        "3. 分析图片的主题和内容\n\n"
        "请严格按照以下JSON格式回复：\n"
        '{"relevant": true/false, "extracted_text": "提取的文字内容或null", "reason": "详细判断理由"}'
    )
    
    try:
        # 处理图片
        processed_images = []
        for i, url in enumerate(image_urls, 1):
            logger.info(f"正在处理第{i}张图片: {url}")
            image_data = image_processor.download_and_encode_image(url, compress=True)
            if image_data and image_data.get('base64'):
                processed_images.append(image_data)
                logger.debug(f"图片{i}处理成功，大小: {image_data['size']} 字节")
            else:
                logger.warning(f"图片{i}处理失败: {url}")
        
        if not processed_images:
            return {
                "relevant": False,
                "extracted_text": None,
                "reason": "所有图片都无法处理",
                "processed_images": 0
            }
        
        # 构建用户提示
        user_content = [{
            "type": "text",
            "text": f"标题：{title}\n\n请分析这些图片是否与标题相关，并提取图片中的文字信息。"
        }]
        
        # 添加图片到消息内容
        for image_data in processed_images:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_data['media_type']};base64,{image_data['base64']}"
                }
            })
        
        # 调用模型
        response = client.chat.completions.create(
            model=_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=1000
        )
        
        # 解析结果
        raw_response = response.choices[0].message.content
        result = json.loads(raw_response)
        
        return {
            "relevant": bool(result.get("relevant", False)),
            "extracted_text": result.get("extracted_text") or None,
            "reason": result.get("reason", "无具体理由"),
            "processed_images": len(processed_images)
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}, 原始响应: {raw_response}")
        return {
            "relevant": False,
            "extracted_text": None,
            "reason": f"JSON解析错误: {str(e)}",
            "processed_images": len(processed_images) if 'processed_images' in locals() else 0
        }
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        return {
            "relevant": False,
            "extracted_text": None,
            "reason": f"分析异常: {str(e)}",
            "processed_images": 0
        }


def analyze_note_relevance(
    title: str,
    content: str,
    images: Optional[list] = None,
) -> dict:
    """
    判断笔记内容是否与标题相关，若相关则提取文字信息。
    如果提供了图片，则优先使用图片分析功能。

    Args:
        title:   笔记标题
        content: 笔记正文内容
        images:  图片 URL 列表（可选）

    Returns:
        {
            "relevant":       bool,        # 内容是否与标题相关
            "extracted_text": str | None,  # 相关时提取的文字信息，不相关时为 None
            "reason":         str,         # 模型给出的判断理由
            "from_images":    bool         # 是否来自图片分析
        }
    """
    # 如果有图片，优先使用图片分析
    if images and len(images) > 0:
        logger.info(f"检测到{len(images)}张图片，使用图片分析模式")
        image_result = analyze_images_relevance(title, images)
        return {
            "relevant": image_result["relevant"],
            "extracted_text": image_result["extracted_text"],
            "reason": image_result["reason"],
            "from_images": True
        }
    
    # 否则使用原来的文本分析逻辑
    client = _get_client()

    system_prompt = (
        "你是一个内容分析助手，负责判断小红书笔记的正文内容是否与标题相关。\n"
        "如果相关，请从内容中提取核心文字信息（去除无关的表情符号、话题标签等噪音），"
        "以简洁、纯文本的形式返回。\n"
        "如果不相关（例如正文为空、只有表情符号或与标题毫无关联），则标记为不相关。\n\n"
        "请以 JSON 格式回复，格式如下：\n"
        '{"relevant": true/false, "extracted_text": "提取的文字或null", "reason": "判断理由"}'
    )
    
    user_prompt = (
        f"标题：{title}\n\n"
        f"正文内容：{content if content.strip() else '(空)'}\n\n"
        "请判断正文是否与标题相关，并提取有效文字信息。"
    )
    
    try:
        response = client.chat.completions.create(
            model=_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    
        raw = response.choices[0].message.content
        result = json.loads(raw)
    
        return {
            "relevant": bool(result.get("relevant", False)),
            "extracted_text": result.get("extracted_text") or None,
            "reason": result.get("reason", ""),
            "from_images": False
        }
    
    except Exception as e:
        logger.error(f"模型调用失败: {e}")
        return {
            "relevant": False,
            "extracted_text": None,
            "reason": f"模型调用异常: {e}",
            "from_images": False
        }
