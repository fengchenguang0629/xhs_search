"""
生产环境 WSGI 入口
使用: gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
"""
import os
import sys
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app, init_app

# 初始化应用
logger.info("正在初始化 Flask 应用...")
if not init_app():
    logger.error("应用初始化失败")
    sys.exit(1)

logger.info("WSGI 应用已准备好进行部署")

if __name__ == '__main__':
    app.run()
