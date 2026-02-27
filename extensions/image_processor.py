#!/usr/bin/env python3
"""
小红书图片链接处理工具
将小红书API返回的图片链接转为大模型可读的base64格式
支持图片压缩以减少 token 消耗
"""

import base64
import io
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from PIL import Image


class ImageProcessor:
    """处理小红书图片链接，转为base64或其他可读格式"""

    # 默认压缩配置
    DEFAULT_MAX_WIDTH = 800  # 最大宽度
    DEFAULT_MAX_HEIGHT = 800  # 最大高度
    DEFAULT_QUALITY = 75  # JPEG 质量 (1-100)

    def __init__(
        self,
        timeout: int = 10,
        max_width: int = DEFAULT_MAX_WIDTH,
        max_height: int = DEFAULT_MAX_HEIGHT,
        quality: int = DEFAULT_QUALITY,
        max_images_per_note: int = 3,  # 每篇笔记最多处理图片数
    ):
        """
        初始化图片处理器

        Args:
            timeout: 下载图片的超时时间（秒）
            max_width: 压缩后最大宽度
            max_height: 压缩后最大高度
            quality: JPEG 压缩质量 (1-100)
            max_images_per_note: 每篇笔记最多处理的图片数
        """
        self.timeout = timeout
        self.max_width = max_width
        self.max_height = max_height
        self.quality = quality
        self.max_images_per_note = max_images_per_note
        self.session = requests.Session()
        # 设置请求头，模拟浏览器行为
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def compress_image(
        self,
        image_data: bytes,
        max_width: int = None,
        max_height: int = None,
        quality: int = None
    ) -> bytes:
        """
        压缩图片以减少大小

        Args:
            image_data: 原始图片字节
            max_width: 最大宽度
            max_height: 最大高度
            quality: JPEG 质量

        Returns:
            压缩后的图片字节
        """
        max_width = max_width or self.max_width
        max_height = max_height or self.max_height
        quality = quality or self.quality

        try:
            img = Image.open(io.BytesIO(image_data))

            # 转换为 RGB（如果是 RGBA 或其他模式）
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # 计算缩放后的尺寸
            width, height = img.size
            if width > max_width or height > max_height:
                ratio = min(max_width / width, max_height / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # 压缩为 JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()

        except Exception as e:
            print(f"[警告] 图片压缩失败: {e}")
            # 压缩失败返回原始数据
            return image_data

    def compress_image_file(
        self,
        image_source: Union[str, Path, bytes, Image.Image],
        max_width: int = None,
        max_height: int = None,
        quality: int = None,
        output_format: str = 'JPEG'
    ) -> bytes:
        """
        通用图片压缩方法，支持多种输入类型

        Args:
            image_source: 图片源，可以是：
                - 文件路径（str 或 Path）
                - 图片字节数据（bytes）
                - PIL Image 对象
            max_width: 压缩后最大宽度，默认使用实例配置
            max_height: 压缩后最大高度，默认使用实例配置
            quality: 压缩质量 (1-100)，默认使用实例配置
            output_format: 输出格式，支持 'JPEG', 'PNG', 'WEBP' 等

        Returns:
            压缩后的图片字节数据

        Raises:
            FileNotFoundError: 当文件路径不存在时
            ValueError: 当输入类型不支持时
        """
        max_width = max_width or self.max_width
        max_height = max_height or self.max_height
        quality = quality or self.quality

        try:
            # 根据输入类型加载图片
            if isinstance(image_source, (str, Path)):
                # 从文件路径加载
                image_path = Path(image_source)
                if not image_path.exists():
                    raise FileNotFoundError(f"图片文件不存在: {image_path}")
                img = Image.open(image_path)
            elif isinstance(image_source, bytes):
                # 从字节数据加载
                img = Image.open(io.BytesIO(image_source))
            elif isinstance(image_source, Image.Image):
                # 直接使用 PIL Image 对象
                img = image_source
            else:
                raise ValueError(f"不支持的图片源类型: {type(image_source)}")

            # 转换颜色模式
            if output_format == 'JPEG':
                # JPEG 不支持透明度，转换为 RGB
                if img.mode in ('RGBA', 'P', 'LA'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            elif output_format == 'PNG' and img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')

            # 计算缩放比例
            width, height = img.size
            if width > max_width or height > max_height:
                ratio = min(max_width / width, max_height / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # 压缩并保存到字节流
            output = io.BytesIO()
            save_kwargs = {'format': output_format, 'optimize': True}
            
            if output_format == 'JPEG':
                save_kwargs['quality'] = quality
            elif output_format == 'PNG':
                save_kwargs['compress_level'] = 9  # PNG 最大压缩级别
            elif output_format == 'WEBP':
                save_kwargs['quality'] = quality
                save_kwargs['method'] = 6  # 压缩方法 (0-6, 6最慢但最小)

            img.save(output, **save_kwargs)
            compressed_data = output.getvalue()

            print(f"[信息] 图片压缩完成: {width}x{height} -> {img.size[0]}x{img.size[1]}, "
                  f"格式: {output_format}, 大小: {len(compressed_data)} 字节")

            return compressed_data

        except Exception as e:
            print(f"[错误] 图片压缩失败: {e}")
            # 如果输入是字节数据且压缩失败，返回原始数据
            if isinstance(image_source, bytes):
                return image_source
            raise

    def image_to_base64(
        self,
        image_source: Union[str, Path, bytes, Image.Image],
        compress: bool = False,
        max_width: int = None,
        max_height: int = None,
        quality: int = None,
        output_format: str = 'JPEG'
    ) -> str:
        """
        将图片转换为base64编码字符串

        Args:
            image_source: 图片源，可以是：
                - 文件路径（str 或 Path）
                - 图片字节数据（bytes）
                - PIL Image 对象
            compress: 是否压缩图片
            max_width: 压缩后最大宽度（仅在compress=True时有效）
            max_height: 压缩后最大高度（仅在compress=True时有效）
            quality: 压缩质量（仅在compress=True时有效）
            output_format: 输出格式（仅在compress=True时有效）

        Returns:
            base64编码的字符串

        Examples:
            >>> processor = ImageProcessor()
            >>> # 从文件路径
            >>> base64_str = processor.image_to_base64('/path/to/image.jpg')
            >>> # 从字节数据
            >>> with open('image.jpg', 'rb') as f:
            ...     base64_str = processor.image_to_base64(f.read())
            >>> # 压缩后转base64
            >>> base64_str = processor.image_to_base64('image.jpg', compress=True, quality=60)
        """
        try:
            # 如果需要压缩
            if compress:
                image_data = self.compress_image_file(
                    image_source,
                    max_width=max_width,
                    max_height=max_height,
                    quality=quality,
                    output_format=output_format
                )
            else:
                # 不压缩，直接获取字节数据
                if isinstance(image_source, (str, Path)):
                    image_path = Path(image_source)
                    if not image_path.exists():
                        raise FileNotFoundError(f"图片文件不存在: {image_path}")
                    with open(image_path, 'rb') as f:
                        image_data = f.read()
                elif isinstance(image_source, bytes):
                    image_data = image_source
                elif isinstance(image_source, Image.Image):
                    # PIL Image 对象需要转为字节
                    output = io.BytesIO()
                    img_format = image_source.format or 'PNG'
                    image_source.save(output, format=img_format)
                    image_data = output.getvalue()
                else:
                    raise ValueError(f"不支持的图片源类型: {type(image_source)}")

            # 转为base64
            base64_str = base64.b64encode(image_data).decode('utf-8')
            return base64_str

        except Exception as e:
            print(f"[错误] 转换base64失败: {e}")
            raise

    def download_and_encode_image(
        self,
        image_url: str,
        compress: bool = True
    ) -> Optional[Dict[str, str | int]]:
        """
        下载图片并转为base64编码（可选压缩）

        Args:
            image_url: 小红书图片链接
            compress: 是否压缩图片

        Returns:
            包含base64和媒体类型的字典，格式为:
            {
                "base64": "base64编码字符串",
                "media_type": "image/jpeg",
                "url": "原始URL",
                "size": 压缩后大小,
                "original_size": 原始大小（如果压缩了）
            }
            如果下载失败返回None
        """
        try:
            # 发送请求获取图片
            response = self.session.get(image_url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            original_size = len(response.content)
            image_data = response.content

            # 压缩图片
            if compress:
                image_data = self.compress_image(image_data)

            # 转为base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            result = {
                "base64": image_base64,
                "media_type": "image/jpeg",  # 统一转为 JPEG
                "url": image_url,
                "size": len(image_data)
            }

            # 如果压缩了，记录原始大小
            if compress and len(image_data) != original_size:
                result["original_size"] = original_size
                compression_ratio = (1 - len(image_data) / original_size) * 100
                print(f"[信息] 图片压缩: {original_size} -> {len(image_data)} 字节 (减少 {compression_ratio:.1f}%)")

            return result

        except requests.RequestException as e:
            print(f"[警告] 下载图片失败 {image_url}: {e}")
            return None
        except Exception as e:
            print(f"[错误] 处理图片异常 {image_url}: {e}")
            return None

    def download_and_encode_image_original(
        self,
        image_url: str
    ) -> Optional[Dict[str, str | int]]:
        """
        下载图片并转为base64编码（不压缩，保持原格式）

        Args:
            image_url: 小红书图片链接

        Returns:
            包含base64和媒体类型的字典
        """
        return self.download_and_encode_image(image_url, compress=False)

    def process_images_in_note(
        self,
        note: Dict,
        max_images: int = None
    ) -> Dict:
        """
        处理笔记中的所有图片

        Args:
            note: 笔记数据字典，包含 'images' 字段
            max_images: 每篇笔记最多处理的图片数（可选）

        Returns:
            返回处理后的笔记，添加了 'processed_images' 字段
        """
        if 'images' not in note or not note['images']:
            return note

        # 限制每篇笔记的图片数量
        max_images = max_images or self.max_images_per_note
        image_urls = note['images'][:max_images]  # 只处理前 N 张

        if len(note['images']) > max_images:
            print(f"[信息] 笔记图片数量: {len(note['images'])} -> 仅处理前 {max_images} 张")

        processed_images = []

        for image_url in image_urls:
            image_data = self.download_and_encode_image(image_url, compress=True)
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

    def process_notes_batch(
        self,
        notes: List[Dict],
        max_images_per_note: int = None
    ) -> List[Dict]:
        """
        批量处理笔记中的图片

        Args:
            notes: 笔记列表
            max_images_per_note: 每篇笔记最多处理的图片数

        Returns:
            处理后的笔记列表
        """
        processed_notes = []
        for i, note in enumerate(notes, 1):
            processed_note = self.process_images_in_note(
                note,
                max_images=max_images_per_note
            )
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
                "media_type": image_data.get('media_type', 'image/jpeg'),
                "data": image_data['base64']
            }
        }

    def build_claude_message_content(
        self,
        text: str,
        images: Optional[List[Dict]] = None,
        max_images: int = None
    ) -> List[Dict]:
        """
        构建Claude API的message content

        Args:
            text: 文本内容
            images: 图片列表（从process_images_in_note返回的processed_images）
            max_images: 最大图片数

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
            max_images = max_images or self.max_images_per_note
            for image_data in images[:max_images]:
                image_content = self.get_image_for_claude(image_data)
                if image_content:
                    content.append(image_content)

        return content


# 快捷函数
def process_xhs_images(
    notes: List[Dict],
    timeout: int = 10,
    max_images_per_note: int = 3,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 75
) -> List[Dict]:
    """
    快捷函数：处理小红书笔记中的所有图片（带压缩）

    Args:
        notes: 小红书API返回的笔记列表
        timeout: 下载超时时间
        max_images_per_note: 每篇笔记最多处理的图片数
        max_width: 压缩后最大宽度
        max_height: 压缩后最大高度
        quality: JPEG 压缩质量

    Returns:
        处理后的笔记列表，每条笔记增加 'processed_images' 字段
    """
    processor = ImageProcessor(
        timeout=timeout,
        max_images_per_note=max_images_per_note,
        max_width=max_width,
        max_height=max_height,
        quality=quality
    )
    return processor.process_notes_batch(notes)


def get_image_base64(
    image_url: str,
    timeout: int = 10,
    compress: bool = True,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 75
) -> Optional[Dict[str, str | int]]:
    """
    快捷函数：获取单张图片的base64编码（可选压缩）

    Args:
        image_url: 图片URL
        timeout: 下载超时时间
        compress: 是否压缩
        max_width: 压缩后最大宽度
        max_height: 压缩后最大高度
        quality: JPEG 压缩质量

    Returns:
        包含base64的字典，或None（失败时）
    """
    processor = ImageProcessor(
        timeout=timeout,
        max_width=max_width,
        max_height=max_height,
        quality=quality
    )
    return processor.download_and_encode_image(image_url, compress=compress)


def compress_image(
    image_source: Union[str, Path, bytes, Image.Image],
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 75,
    output_format: str = 'JPEG'
) -> bytes:
    """
    快捷函数：压缩图片

    Args:
        image_source: 图片源，可以是文件路径、字节数据或PIL Image对象
        max_width: 压缩后最大宽度
        max_height: 压缩后最大高度
        quality: 压缩质量 (1-100)
        output_format: 输出格式 ('JPEG', 'PNG', 'WEBP')

    Returns:
        压缩后的图片字节数据

    Examples:
        >>> # 压缩本地文件
        >>> compressed = compress_image('photo.jpg', max_width=1024, quality=80)
        >>> # 压缩字节数据
        >>> with open('photo.jpg', 'rb') as f:
        ...     compressed = compress_image(f.read(), quality=60)
        >>> # 保存压缩后的图片
        >>> with open('photo_compressed.jpg', 'wb') as f:
        ...     f.write(compressed)
    """
    processor = ImageProcessor(
        max_width=max_width,
        max_height=max_height,
        quality=quality
    )
    return processor.compress_image_file(
        image_source,
        output_format=output_format
    )


def convert_image_to_base64(
    image_source: Union[str, Path, bytes, Image.Image],
    compress: bool = False,
    max_width: int = 800,
    max_height: int = 800,
    quality: int = 75,
    output_format: str = 'JPEG'
) -> str:
    """
    快捷函数：将图片转换为base64编码字符串

    Args:
        image_source: 图片源，可以是文件路径、字节数据或PIL Image对象
        compress: 是否压缩图片
        max_width: 压缩后最大宽度（仅在compress=True时有效）
        max_height: 压缩后最大高度（仅在compress=True时有效）
        quality: 压缩质量（仅在compress=True时有效）
        output_format: 输出格式（仅在compress=True时有效）

    Returns:
        base64编码的字符串

    Examples:
        >>> # 直接转换本地图片
        >>> base64_str = convert_image_to_base64('photo.jpg')
        >>> # 压缩后转换
        >>> base64_str = convert_image_to_base64('photo.jpg', compress=True, quality=60)
        >>> # 用于API调用
        >>> data_uri = f"data:image/jpeg;base64,{base64_str}"
    """
    processor = ImageProcessor(
        max_width=max_width,
        max_height=max_height,
        quality=quality
    )
    return processor.image_to_base64(
        image_source,
        compress=compress,
        output_format=output_format
    )
