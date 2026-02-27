import os
import sys

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from loguru import logger

# 添加父目录到路径以导入 main 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import Data_Spider
from dataspider import FormattedDataSpider
from xhs_utils.common_util import init
from xhs_utils.cookie_util import trans_cookies
from extensions.model_client import analyze_note_relevance

# 获取当前 web 目录路径
WEB_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=WEB_DIR, static_url_path='')
# 启用 CORS 支持跨域请求
CORS(app, resources={r"/api/*": {"origins": "*"}})

global_cookies = None      # 全局 cookies
data_spider = None         # 爬虫实例
formatted_spider = None    # 格式化爬虫实例

def init_app():
    """初始化 Flask 应用"""
    global global_cookies, data_spider, formatted_spider
    try:
        cookies_str, base_path = init()
        global_cookies = cookies_str
        data_spider = Data_Spider()
        formatted_spider = FormattedDataSpider()
        logger.info("Flask 应用初始化成功")
        return True
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        return False

@app.route('/', methods=['GET'])
def index():
    """提供主页"""
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({'status': 'healthy'}), 200

def save_cookies_to_env(cookies_str):
    """将 cookies 保存到 .env 文件"""
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(f"COOKIES='{cookies_str}'\n")
        logger.info(f"Cookies 已保存到 {env_path}")
        return True
    except Exception as e:
        logger.error(f"保存 cookies 到 .env 失败: {e}")
        return False

@app.route('/api/cookies', methods=['POST'])
def set_cookies():
    """
    设置 Cookies
    请求体: {"cookies": "cookie_string"}
    """
    try:
        data = request.get_json()
        if not data or 'cookies' not in data:
            return jsonify({'error': 'cookies 字段缺失'}), 400
        
        cookies_str = data['cookies']
        trans_cookies(cookies_str)  # 验证 cookies 格式
        
        global global_cookies
        global_cookies = cookies_str

        # 保存到 .env 文件
        save_cookies_to_env(cookies_str)

        logger.info("Cookies 已更新")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"设置 cookies 失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/spider/note', methods=['POST'])
def spider_note():
    """
    爬取单个笔记
    请求体: {"note_url": "...", "proxies": null}
    """
    try:
        if not global_cookies:
            return jsonify({'error': 'Cookies 未设置'}), 400
        
        data = request.get_json()
        if not data or 'note_url' not in data:
            return jsonify({'error': 'note_url 字段缺失'}), 400
        
        note_url = data['note_url']
        proxies = data.get('proxies', None)
        
        success, msg, note_info = data_spider.spider_note(note_url, global_cookies, proxies)
        
        if success:
            return jsonify({'status': 'success', 'data': note_info}), 200
        return jsonify({'error': str(msg)}), 400
    except Exception as e:
        logger.error(f"爬取笔记失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/spider/user-notes', methods=['POST'])
def spider_user_notes():
    """
    爬取用户的所有笔记
    请求体: {
        "user_url": "...",
        "save_choice": "excel|media|all",
        "excel_name": "文件名"
    }
    """
    try:
        if not global_cookies:
            return jsonify({'error': 'Cookies 未设置'}), 400
        
        data = request.get_json()
        if not data or 'user_url' not in data or 'save_choice' not in data:
            return jsonify({'error': '缺少必需字段'}), 400
        
        user_url = data['user_url']
        save_choice = data['save_choice']
        excel_name = data.get('excel_name', '')
        proxies = data.get('proxies', None)
        
        # 如果保存为 Excel，需要提供文件名
        if (save_choice in ['all', 'excel']) and not excel_name:
            return jsonify({'error': 'excel_name 为必需'}), 400
        
        _, base_path = init()
        
        note_list, success, msg = data_spider.spider_user_all_note(
            user_url, global_cookies, base_path, save_choice, excel_name, proxies
        )
        
        if success or note_list:
            return jsonify({'status': 'success', 'count': len(note_list), 'urls': note_list}), 200
        return jsonify({'error': str(msg)}), 400
    except Exception as e:
        logger.error(f"爬取用户笔记失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/spider/search-notes', methods=['POST'])
def spider_search_notes():
    """
    搜索并爬取笔记
    请求体: {
        "query": "搜索关键词",
        "require_num": 10,
        "save_choice": "excel|media|all",
        "excel_name": "文件名"
    }
    """
    try:
        if not global_cookies:
            return jsonify({'error': 'Cookies 未设置'}), 400
        
        data = request.get_json()
        if not data or not all(k in data for k in ['query', 'require_num', 'save_choice']):
            return jsonify({'error': '缺少必需字段'}), 400
        
        query = data['query']
        require_num = data['require_num']
        save_choice = data['save_choice']
        excel_name = data.get('excel_name', '')
        
        # 如果保存为 Excel，需要提供文件名
        if (save_choice in ['all', 'excel']) and not excel_name:
            return jsonify({'error': 'excel_name 为必需'}), 400
        
        _, base_path = init()
        
        note_list, success, msg = data_spider.spider_some_search_note(
            query, require_num, global_cookies, base_path, save_choice,
            data.get('sort_type_choice', 0),  # 0=综合, 1=最新, 2=点赞, 3=评论, 4=收藏
            data.get('note_type', 0),         # 0=全部, 1=视频, 2=普通
            data.get('note_time', 0),         # 0=全部, 1=1天, 2=1周, 3=6月
            data.get('note_range', 0),        # 0=全部, 1=已看过, 2=未看过, 3=已关注
            data.get('pos_distance', 0),      # 0=全部, 1=同城, 2=附近
            data.get('geo', None),            # 地理位置: {"latitude": x, "longitude": y}
            excel_name,
            data.get('proxies', None)
        )
        
        if success or note_list:
            return jsonify({'status': 'success', 'count': len(note_list), 'urls': note_list}), 200
        return jsonify({'error': str(msg)}), 400
    except Exception as e:
        logger.error(f"搜索笔记失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notes/search', methods=['POST'])
def note_search_formatted():
    """
    搜索笔记并返回格式化的 JSON 数据
    请求体: {
        "query": "搜索关键词",
        "require_num": 10,
        "sort_type_choice": 0,
        "note_type": 2,
        "note_time": 0,
        "note_range": 0,
        "pos_distance": 0,
        "geo": null
    }
    """
    try:
        if not global_cookies:
            return jsonify({'error': 'Cookies 未设置'}), 400
        
        data = request.get_json()
        if not data or 'query' not in data or 'require_num' not in data:
            return jsonify({'error': '缺少必需字段: query, require_num'}), 400
        
        query = data['query']
        require_num = data['require_num']
        
        formatted_notes = formatted_spider.search_and_format(
            query, require_num, global_cookies,
            data.get('sort_type_choice', 0),
            data.get('note_type', 2),
            data.get('note_time', 0),
            data.get('note_range', 0),
            data.get('pos_distance', 0),
            data.get('geo', None)
        )
        
        logger.info(f"格式化搜索结果: {query}, 数量: {len(formatted_notes)}")
        return jsonify({'status': 'success', 'count': len(formatted_notes), 'data': formatted_notes}), 200
    except Exception as e:
        logger.error(f"格式化搜索失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notes/search-with-extract', methods=['POST'])
def note_search_with_extract():
    """
    搜索笔记并智能提取信息：
    - 正文长度 > 200 字：内容充足，直接返回正文，images 置为空列表
    - 正文长度 <= 200 字：内容不足，对图片进行 OCR 提取文字，images 替换为提取到的文字列表

    请求体:
    {
        "query":           "搜索关键词（必填）",
        "require_num":     10,
        "sort_type_choice": 0,
        "note_type":       2,
        "note_time":       0,
        "note_range":      0,
        "pos_distance":    0,
        "geo":             null
    }
    返回:
    {
        "status": "success",
        "count":  10,
        "data": [
            {
                "id":            "笔记ID",
                "url":           "笔记URL",
                "title":         "标题",
                "content":       "正文",
                "images":        ["提取的文字1", ...] 或 [],
                "liked_count":   0,
                "comment_count": 0,
                "share_count":   0,
                "image_extracted": true/false  # 是否对图片做了文字提取
            },
            ...
        ]
    }
    """
    # 正文长度阈值：超过此值则认为内容充足，无需提取图片文字
    CONTENT_LENGTH_THRESHOLD = 200

    try:
        if not global_cookies:
            return jsonify({'error': 'Cookies 未设置'}), 400

        data = request.get_json(force=True, silent=True)
        if not data or 'query' not in data or 'require_num' not in data:
            return jsonify({'error': '缺少必需字段: query, require_num'}), 400

        query      = data['query']
        require_num = data['require_num']

        # 1. 搜索并格式化笔记
        formatted_notes = formatted_spider.search_and_format(
            query, require_num, global_cookies,
            data.get('sort_type_choice', 0),
            data.get('note_type', 2),
            data.get('note_time', 0),
            data.get('note_range', 0),
            data.get('pos_distance', 0),
            data.get('geo', None)
        )
        logger.info(f"搜索到 {len(formatted_notes)} 篇笔记，关键词: {query!r}")

        # 2. 逐篇判断是否需要图片文字提取
        result_notes = []
        for note in formatted_notes:
            content        = note.get('content', '') or ''
            title          = note.get('title', '') or ''
            image_urls     = note.get('images', []) or []
            need_extract   = len(content) <= CONTENT_LENGTH_THRESHOLD and len(image_urls) > 0

            if need_extract:
                # 正文内容不足，对图片做 OCR 提取
                logger.info(
                    f"笔记 [{note.get('id')}] 正文仅 {len(content)} 字，"
                    f"对 {len(image_urls)} 张图片进行文字提取"
                )
                analysis = analyze_note_relevance(title, image_urls)
                extracted_text = analysis.get('extracted_text') or ''
                # images 字段替换为提取到的文字列表（按换行拆分，过滤空行）
                images_field    = [t for t in extracted_text.splitlines() if t.strip()] if extracted_text else []
                image_extracted = True
            else:
                # 正文充足或无图片，清空 images 字段
                reason = "正文充足" if len(content) > CONTENT_LENGTH_THRESHOLD else "无图片"
                logger.info(f"笔记 [{note.get('id')}] {reason}（{len(content)} 字），跳过图片提取")
                images_field    = []
                image_extracted = False

            result_notes.append({
                'url':             note.get('url', ''),
                'title':           note.get('title', ''),
                'content':         note.get('content', ''),
                'image_extracted': image_extracted,
                'images':          images_field,
                'liked_count':     note.get('liked_count', 0),
                'comment_count':   note.get('comment_count', 0),
                'share_count':     note.get('share_count', 0),
            })

        return jsonify({'status': 'success', 'count': len(result_notes), 'data': result_notes}), 200

    except Exception as e:
        logger.error(f"搜索并提取失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test/analyze-relevance', methods=['POST'])
def test_analyze_relevance():
    """
    测试 analyze_note_relevance 函数
    请求体:
    {
        "title":  "笔记标题（必填）",
        "images": ["图片URL1", "图片URL2"]  // 必填
    }
    返回:
    {
        "status": "success",
        "data": {
            "relevant":         true/false,
            "extracted_text":   "提取的文字或 null",
            "processed_images": 实际处理的图片数量
        }
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'error': '请求体不能为空，需要 Content-Type: application/json 且合法的 JSON 格式'}), 400
        if 'title' not in data or 'images' not in data:
            return jsonify({'error': '缺少必需字段: title, images'}), 400

        title  = data['title']
        images = data['images']

        if not isinstance(images, list):
            return jsonify({'error': 'images 必须是数组'}), 400

        logger.info(f"测试 analyze_note_relevance — 标题: {title!r}, 图片数: {len(images)}")
        result = analyze_note_relevance(title, images)
        return jsonify({'status': 'success', 'data': result}), 200

    except Exception as e:
        logger.error(f"analyze_note_relevance 测试失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    """404 处理"""
    return jsonify({'error': '端点不存在'}), 404

@app.errorhandler(500)
def error(e):
    """500 错误处理"""
    logger.error(f"服务器错误: {e}")
    return jsonify({'error': '内部错误'}), 500

if __name__ == '__main__':
    if not init_app():
        sys.exit(1)
    app.run(host='0.0.0.0', port=5000, debug=False)