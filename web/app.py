from flask import Flask, request, jsonify
from loguru import logger
import os
import sys

# 添加父目录到路径以导入 main 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import Data_Spider
from dataspider import FormattedDataSpider
from xhs_utils.common_util import init
from xhs_utils.cookie_util import trans_cookies

app = Flask(__name__)
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

@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({'status': 'healthy'}), 200

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
        "note_type": 0,
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
            data.get('note_type', 0),
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
    app.run(host='0.0.0.0', port=5001, debug=False)
