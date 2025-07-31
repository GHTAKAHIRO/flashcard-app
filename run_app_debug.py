#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from app import app

if __name__ == '__main__':
    app.debug = True
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    print("🚀 Flaskアプリケーションをデバッグモードで起動します...")
    print("📝 ログが詳細に出力されます")
    print("🌐 http://localhost:5000 でアクセス可能です")
    app.run(host='0.0.0.0', port=5000, debug=True) 