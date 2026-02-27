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

import requests
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
            "processed_images": int     # 实际处理的图片数量
        }
    """
    if not image_urls:
        return {
            "relevant": False,
            "extracted_text": None,
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
        '{"relevant": true/false, "extracted_text": "提取的文字内容或null"}'
    )
    
    try:
        # 处理图片
        processed_images = []
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        for i, url in enumerate(image_urls, 1):
            logger.info(f"正在处理第{i}张图片: {url}")
            try:
                # 1. 下载图片原始字节
                resp = session.get(url, timeout=10, allow_redirects=True)
                resp.raise_for_status()
                raw_bytes = resp.content
                original_size = len(raw_bytes)

                # 2. 使用 compress_image_file 压缩图片
                compressed_bytes = image_processor.compress_image_file(
                    raw_bytes,
                    output_format='JPEG'
                )

                # 3. 使用 image_to_base64 转换为 base64 字符串
                base64_str = image_processor.image_to_base64(
                    compressed_bytes,
                    compress=False  # 已经压缩过，无需再次压缩
                )

                image_data = {
                    "base64": base64_str,
                    "media_type": "image/jpeg",
                    "url": url,
                    "size": len(compressed_bytes),
                    "original_size": original_size
                }

                processed_images.append(image_data)
                logger.debug(
                    f"图片{i}处理成功 — 原始: {original_size} 字节, "
                    f"压缩后: {len(compressed_bytes)} 字节 "
                    f"(减少 {(1 - len(compressed_bytes) / original_size) * 100:.1f}%)"
                )
            except Exception as img_err:
                logger.warning(f"图片{i}处理失败: {url} — {img_err}")
        
        if not processed_images:
            return {
                "relevant": False,
                "extracted_text": None,
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
            "processed_images": len(processed_images)
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}, 原始响应: {raw_response}")
        return {
            "relevant": False,
            "extracted_text": None,
            "processed_images": len(processed_images) if 'processed_images' in locals() else 0
        }
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        return {
            "relevant": False,
            "extracted_text": None,
            "processed_images": 0
        }


def analyze_note_relevance(
    title: str,
    images: List[str],
) -> dict:
    """
    分析笔记图片与标题的相关性，并提取图片中的文字信息。

    Args:
        title:  笔记标题
        images: 图片 URL 列表

    Returns:
        {
            "relevant":         bool,       # 图片是否与标题相关
            "extracted_text":   str | None, # 从图片中提取的文字信息
            "processed_images": int         # 实际处理的图片数量
        }
    """
    if not images:
        return {
            "relevant": False,
            "extracted_text": None,
            "processed_images": 0
        }

    logger.info(f"开始分析 {len(images)} 张图片，标题: {title!r}")
    return analyze_images_relevance(title, images)
