#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from app import app

if __name__ == '__main__':
    # デバッグモードを有効にする
    app.debug = True
    
    # ログレベルを設定
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app_debug.log', encoding='utf-8')
        ]
    )
    
    # アプリケーション固有のログ設定
    app.logger.setLevel(logging.DEBUG)
    
    print("🚀 Flaskアプリケーションをデバッグモードで起動します...")
    print("📝 ログが詳細に出力されます")
    print("📄 ログファイル: app_debug.log")
    print("🌐 http://localhost:5000 でアクセス可能です")
    print("🔧 管理者ログイン: ユーザー名=admin, パスワード=admin")
    
    # アプリケーションを起動
    app.run(host='0.0.0.0', port=5000, debug=True) 