#!/usr/bin/env python3
"""
小红书搜索API客户端
集成了图片处理功能，可以直接返回包含base64图片的笔记数据
独立使用，无需依赖外部项目
"""

from typing import Dict, Optional

import requests

# 支持多种导入方式
try:
    from .image_processor import ImageProcessor
except ImportError:
    try:
        from image_processor import ImageProcessor
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from image_processor import ImageProcessor


class XHSSearchClient:
    """小红书搜索API客户端"""

    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 30):
        """
        初始化搜索客户端

        Args:
            base_url: API服务地址
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.image_processor = ImageProcessor(timeout=10)

    def search(
        self,
        query: str,
        require_num: int = 10,
        sort_type_choice: int = 0,
        note_type: int = 0,
        note_time: int = 0,
        note_range: int = 0,
        pos_distance: int = 0,
        geo: Optional[str] = None,
        process_images: bool = True
    ) -> Dict:
        """
        搜索小红书笔记

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            sort_type_choice: 排序方式
            note_type: 笔记类型
            note_time: 时间范围
            note_range: 范围
            pos_distance: 距离
            geo: 地理位置
            process_images: 是否处理图片为base64格式

        Returns:
            API响应数据
        """
        url = f"{self.base_url}/api/notes/search"

        payload = {
            "query": query,
            "require_num": require_num,
            "sort_type_choice": sort_type_choice,
            "note_type": note_type,
            "note_time": note_time,
            "note_range": note_range,
            "pos_distance": pos_distance,
            "geo": geo
        }

        try:
            print(f"[信息] 发送搜索请求: {query} (数量: {require_num})")
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

            result = response.json()

            if result.get("status") == "success" and process_images:
                print(f"[信息] 开始处理 {len(result.get('data', []))} 条笔记的图片")
                result['data'] = self.image_processor.process_notes_batch(result['data'])
                print(f"[信息] 图片处理完成")

            return result

        except requests.RequestException as e:
            print(f"[错误] API请求失败: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data": []
            }
        except Exception as e:
            print(f"[错误] 处理响应异常: {e}")
            return {
                "status": "error",
                "message": str(e),
                "data": []
            }

    def search_no_images(
        self,
        query: str,
        require_num: int = 10,
        **kwargs
    ) -> Dict:
        """
        搜索笔记，不处理图片（快速模式）

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            **kwargs: 其他参数

        Returns:
            API响应数据
        """
        return self.search(query, require_num, process_images=False, **kwargs)


def search_xhs_notes(
    query: str,
    require_num: int = 10,
    process_images: bool = True,
    api_url: str = "http://localhost:5000"
) -> Dict:
    """
    快捷函数：搜索小红书笔记

    Args:
        query: 搜索关键词
        require_num: 返回笔记数量
        process_images: 是否转换图片为base64
        api_url: API服务地址

    Returns:
        搜索结果，包含处理后的笔记和图片
    """
    client = XHSSearchClient(base_url=api_url)
    return client.search(query, require_num, process_images=process_images)


if __name__ == "__main__":
    # 测试例子
    print("测试搜索API...")
    result = search_xhs_notes("产后恢复", require_num=2, process_images=True)

    if result.get("status") == "success":
        print(f"✓ 搜索成功，获得 {len(result['data'])} 条笔记")
        for i, note in enumerate(result['data'], 1):
            print(f"\n笔记 {i}: {note.get('title', '无标题')}")
            if 'processed_images' in note:
                print(f"  图片数量: {len(note['processed_images'])}")
                for j, img in enumerate(note['processed_images'], 1):
                    if img.get('base64'):
                        print(f"    图片 {j}: ✓ base64编码 ({img['size']} 字节)")
                    else:
                        print(f"    图片 {j}: ✗ 处理失败 - {img.get('error', '未知错误')}")
    else:
        print(f"✗ 搜索失败: {result.get('message')}")

