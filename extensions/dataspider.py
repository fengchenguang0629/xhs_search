import json
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.data_util import handle_note_info
from extensions.model_client import analyze_note_relevance

# content 长度阈值：低于此值时调用模型分析
CONTENT_MIN_LENGTH = 200


class FormattedDataSpider:
    """格式化数据爬虫，提供格式化的 JSON 输出"""

    def __init__(self):
        self.xhs_apis = XHS_Apis()

    def get_note_info(self, note_url: str, cookies_str: str):
        """
        爬取单个笔记信息
        :param note_url: 笔记 URL
        :param cookies_str: cookies
        :return: 笔记信息或 None
        """
        try:
            success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, None)
            if not success:
                logger.warning(f'API 返回失败 {note_url}: {msg}')
                return None

            # 检查响应结构
            if not note_info or 'data' not in note_info or 'items' not in note_info['data']:
                logger.warning(f'笔记信息结构异常 {note_url}: 缺少必需字段')
                return None

            items = note_info['data']['items']
            if not items or len(items) == 0:
                logger.warning(f'笔记信息为空 {note_url}')
                return None

            note_info = items[0]
            note_info['url'] = note_url
            note_info = handle_note_info(note_info)
            logger.info(f'成功爬取笔记: {note_url}')
            return note_info
        except KeyError as e:
            logger.warning(f'笔记字段缺失 {note_url}: {e}（通常是 Cookies 过期或笔记格式变化）')
        except Exception as e:
            logger.error(f'爬取笔记信息失败 {note_url}: {e}')
        return None

    def search_and_format(self, query: str, require_num: int, cookies_str: str, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo: dict = None):
        """
        搜索笔记并返回格式化的 JSON 数据
        :param query: 搜索关键词
        :param require_num: 搜索数量
        :param cookies_str: cookies
        :param sort_type_choice: 排序方式 0=综合, 1=最新, 2=点赞, 3=评论, 4=收藏
        :param note_type: 笔记类型 0=全部, 1=视频, 2=普通
        :param note_time: 时间筛选 0=全部, 1=1天, 2=1周, 3=6月
        :param note_range: 范围筛选 0=全部, 1=已看过, 2=未看过, 3=已关注
        :param pos_distance: 距离筛选 0=全部, 1=同城, 2=附近
        :param geo: 地理位置
        :return: 格式化的笔记列表
        """
        formatted_notes = []
        try:
            # 调用搜索接口
            success, msg, notes = self.xhs_apis.search_some_note(
                query, require_num, cookies_str, sort_type_choice,
                note_type, note_time, note_range, pos_distance, geo, None
            )

            if not success:
                logger.error(f'搜索失败: {msg}')
                return formatted_notes

            # 过滤笔记类型
            notes = list(filter(lambda x: x['model_type'] == "note", notes))
            logger.info(f'搜索关键词 {query} 笔记数量: {len(notes)}')

            # 逐个爬取笔记详细信息并格式化
            for note in notes:
                note_url = f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"
                note_info = self.get_note_info(note_url, cookies_str)

                if note_info:
                    formatted_note = self._format_note(note_info)
                    formatted_notes.append(formatted_note)

        except Exception as e:
            logger.error(f'搜索和格式化失败: {e}')

        return formatted_notes

    def _format_note(self, note_info: dict):
        """
        格式化单个笔记信息。
        当 content 字数 < CONTENT_MIN_LENGTH 时，调用模型分析内容是否与标题相关：
          - 若相关，用模型提取的文字替换 content，并记录分析结果。
          - 若不相关，保留原始 content，并标记分析结果。

        :param note_info: 笔记详细信息
        :return: 格式化后的笔记数据
        """
        note_type = note_info.get('note_type', '')
        title = note_info.get('title', '')
        content = note_info.get('desc', '')

        # 获取图片列表
        images = []
        if note_type == '图集':
            images = note_info.get('image_list', [])

        # 获取视频列表
        videos = []
        if note_type == '视频':
            video_addr = note_info.get('video_addr')
            if video_addr:
                videos = [video_addr]

        # AI 分析：content 字数不足时判断相关性并提取文字
        ai_analyzed = False
        ai_extracted_text = None
        ai_relevant = None

        if len(content) < CONTENT_MIN_LENGTH:
            logger.info(
                f'笔记 content 字数({len(content)}) < {CONTENT_MIN_LENGTH}，'
                f'调用模型分析相关性: 「{title}」'
            )
            try:
                result = analyze_note_relevance(
                    title=title,
                    content=content,
                    images=images,
                )
                ai_analyzed = True
                ai_relevant = result.get('relevant', False)
                ai_extracted_text = result.get('extracted_text')

                if ai_relevant and ai_extracted_text:
                    logger.info(f'模型分析结果：相关，提取文字（原因: {result.get("reason", "")}）')
                    content = ai_extracted_text
                else:
                    logger.info(f'模型分析结果：{"不相关" if not ai_relevant else "相关但无提取文字"}（原因: {result.get("reason", "")}）')
            except Exception as e:
                logger.error(f'AI 分析失败，使用原始 content: {e}')

        print(note_info)
        return {
            'id': note_info.get('note_id', ''),
            'url': note_info.get('note_url', ''),
            'title': title,
            'content': content,
            'note_type': note_type,
            'images': images,
            'videos': videos,
            'liked_count': note_info.get('liked_count', 0),
            'comment_count': note_info.get('comment_count', 0),
            'share_count': note_info.get('share_count', 0),
            'tags': note_info.get('tags', []),
            # AI 分析结果字段
            'ai_analyzed': ai_analyzed,
            'ai_relevant': ai_relevant,
            'ai_extracted_text': ai_extracted_text,
        }
