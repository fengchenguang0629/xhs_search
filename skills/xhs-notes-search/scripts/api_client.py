#!/usr/bin/env python3
"""
小红书搜索API客户端
调用 /api/notes/search-with-extract 接口：
- 服务端已完成图片压缩、base64转换和OCR提取
- 根据正文长度（>200字）自动判断是否提取图片文字
- 直接返回结构化数据，无需客户端额外处理图片
"""

from typing import Dict, List, Optional

import requests


class XHSSearchClient:
    """小红书搜索API客户端"""

    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 120):
        """
        初始化搜索客户端

        Args:
            base_url: API服务地址
            timeout: 请求超时时间（秒），图片OCR处理耗时较长，建议120s以上
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def search(
        self,
        query: str,
        require_num: int = 10,
        sort_type_choice: int = 0,
        note_type: int = 2,
        note_time: int = 0,
        note_range: int = 0,
        pos_distance: int = 0,
        geo: Optional[str] = None,
    ) -> Dict:
        """
        搜索小红书笔记（含智能图片OCR提取）

        服务端处理逻辑：
        - 正文 > 200字：内容充足，images 为空列表，image_extracted=false
        - 正文 ≤ 200字：对图片进行OCR，images 替换为提取的文字行列表，image_extracted=true

        Args:
            query: 搜索关键词
            require_num: 返回笔记数量
            sort_type_choice: 排序方式（0=综合, 1=最新, 2=点赞, 3=评论, 4=收藏）
            note_type: 笔记类型（0=全部, 1=视频, 2=普通）
            note_time: 时间范围（0=全部, 1=1天, 2=1周, 3=6月）
            note_range: 范围（0=全部, 1=已看过, 2=未看过, 3=已关注）
            pos_distance: 距离（0=全部, 1=同城, 2=附近）
            geo: 地理位置

        Returns:
            {
                "status": "success",
                "count": 10,
                "data": [
                    {
                        "id":              "笔记ID",
                        "url":             "笔记URL",
                        "title":           "标题",
                        "content":         "正文",
                        "images":          ["OCR提取的文字行..."] 或 [],
                        "liked_count":     0,
                        "comment_count":   0,
                        "share_count":     0,
                        "image_extracted": true/false
                    },
                    ...
                ]
            }
        """
        url = f"{self.base_url}/api/notes/search-with-extract"

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
            print(f"[信息] 发送搜索请求: {query!r} (数量: {require_num})")
            response = self.session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "success":
                data = result.get("data", [])
                extracted = sum(1 for n in data if n.get("image_extracted"))
                print(f"[信息] 搜索完成: {len(data)} 篇笔记，其中 {extracted} 篇进行了图片文字提取")

            return result

        except requests.RequestException as e:
            print(f"[错误] API请求失败: {e}")
            return {"status": "error", "message": str(e), "data": []}
        except Exception as e:
            print(f"[错误] 处理响应异常: {e}")
            return {"status": "error", "message": str(e), "data": []}


def search_xhs_notes(
    query: str,
    require_num: int = 10,
    api_url: str = "http://localhost:5000"
) -> Dict:
    """
    快捷函数：搜索小红书笔记（含智能图片OCR提取）

    Args:
        query: 搜索关键词
        require_num: 返回笔记数量
        api_url: API服务地址

    Returns:
        搜索结果，images 字段为 OCR 提取的文字或空列表
    """
    client = XHSSearchClient(base_url=api_url)
    return client.search(query, require_num)
