#!/usr/bin/env python3
"""
小红书图片链接处理工具
将小红书API返回的图片链接转为大模型可读的base64格式
无需依赖外部项目，独立使用
"""

import base64
from typing import Dict, List, Optional

import requests


class ImageProcessor:
    """处理小红书图片链接，转为base64或其他可读格式"""

    def __init__(self, timeout: int = 10):
        """
        初始化图片处理器

        Args:
            timeout: 下载图片的超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()
        # 设置请求头，模拟浏览器行为
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def download_and_encode_image(self, image_url: str) -> Optional[Dict[str, str]]:
        """
        下载图片并转为base64编码

        Args:
            image_url: 小红书图片链接

        Returns:
            包含base64和媒体类型的字典，格式为:
            {
                "base64": "base64编码字符串",
                "media_type": "image/webp" 或 "image/jpeg" 等
            }
            如果下载失败返回None
        """
        try:
            # 发送请求获取图片
            response = self.session.get(image_url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            # 获取媒体类型
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            # 简化媒体类型（移除charset等参数）
            if ';' in content_type:
                content_type = content_type.split(';')[0].strip()

            # 转为base64
            image_base64 = base64.b64encode(response.content).decode('utf-8')

            return {
                "base64": image_base64,
                "media_type": content_type,
                "url": image_url,
                "size": len(response.content)
            }

        except requests.RequestException as e:
            print(f"[警告] 下载图片失败 {image_url}: {e}")
            return None
        except Exception as e:
            print(f"[错误] 处理图片异常 {image_url}: {e}")
            return None

    def process_images_in_note(self, note: Dict) -> Dict:
        """
        处理笔记中的所有图片

        Args:
            note: 笔记数据字典，包含 'images' 字段

        Returns:
            返回处理后的笔记，添加了 'processed_images' 字段
        """
        if 'images' not in note or not note['images']:
            return note

        processed_images = []

        for image_url in note['images']:
            image_data = self.download_and_encode_image(image_url)
            if image_data:
                processed_images.append(image_data)
            else:
                # 如果下载失败，保留原始链接
                processed_images.append({
                    "base64": None,
                    "media_type": None,
                    "url": image_url,
                    "size": None,
                    "error": "下载失败，保留链接"
                })

        note['processed_images'] = processed_images
        return note

    def process_notes_batch(self, notes: List[Dict]) -> List[Dict]:
        """
        批量处理笔记中的图片

        Args:
            notes: 笔记列表

        Returns:
            处理后的笔记列表
        """
        processed_notes = []
        for i, note in enumerate(notes, 1):
            processed_note = self.process_images_in_note(note)
            processed_notes.append(processed_note)

        return processed_notes

    def get_image_for_claude(self, image_data: Dict) -> Optional[Dict]:
        """
        将图片转为Claude API可用的格式

        Args:
            image_data: 从download_and_encode_image返回的数据

        Returns:
            Claude messages API 可用的image content dict，如果图片不可用返回None
        """
        if not image_data.get('base64'):
            return None

        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_data.get('media_type', 'image/webp'),
                "data": image_data['base64']
            }
        }

    def build_claude_message_content(
        self,
        text: str,
        images: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        构建Claude API的message content

        Args:
            text: 文本内容
            images: 图片列表（从process_images_in_note返回的processed_images）

        Returns:
            Claude messages API 可用的content列表
        """
        content = []

        # 添加文本
        content.append({
            "type": "text",
            "text": text
        })

        # 添加图片
        if images:
            for image_data in images:
                image_content = self.get_image_for_claude(image_data)
                if image_content:
                    content.append(image_content)

        return content


# 快捷函数
def process_xhs_images(notes: List[Dict], timeout: int = 10) -> List[Dict]:
    """
    快捷函数：处理小红书笔记中的所有图片

    Args:
        notes: 小红书API返回的笔记列表
        timeout: 下载超时时间

    Returns:
        处理后的笔记列表，每条笔记增加 'processed_images' 字段
    """
    processor = ImageProcessor(timeout=timeout)
    return processor.process_notes_batch(notes)


def get_image_base64(image_url: str, timeout: int = 10) -> Optional[Dict]:
    """
    快捷函数：获取单张图片的base64编码

    Args:
        image_url: 图片URL
        timeout: 下载超时时间

    Returns:
        包含base64的字典，或None（失败时）
    """
    processor = ImageProcessor(timeout=timeout)
    return processor.download_and_encode_image(image_url)


if __name__ == "__main__":
    # 测试例子
    test_url = "http://sns-webpic-qc.xhscdn.com/202602231728/d1cc1b153d7d39b9cd2f774c2184b335/1040g2sg31bl2m674gu7049mnn830n33nt88n27o!nd_dft_wlteh_webp_3"

    print("测试图片处理...")
    result = get_image_base64(test_url)

    if result:
        print(f"✓ 成功下载图片")
        print(f"  媒体类型: {result['media_type']}")
        print(f"  文件大小: {result['size']} 字节")
        print(f"  Base64长度: {len(result['base64'])} 字符")
        print(f"  Base64预览: {result['base64'][:50]}...")
    else:
        print("✗ 图片下载失败")

