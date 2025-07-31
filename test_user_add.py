#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def test_user_addition():
    """ユーザー追加をテスト"""
    base_url = "http://localhost:5000"
    
    print("🧪 ユーザー追加テスト開始")
    
    # ログインしてセッションを取得
    login_data = {
        'username': 'admin',  # 管理者ユーザー名
        'password': 'admin123'  # 管理者パスワード
    }
    
    try:
        session = requests.Session()
        
        # ログイン
        print("🔐 管理者ログイン中...")
        login_response = session.post(f"{base_url}/login", data=login_data)
        
        if login_response.status_code != 200:
            print(f"❌ ログイン失敗: {login_response.status_code}")
            return
        
        print("✅ ログイン成功")
        
        # ユーザー追加
        user_data = {
            'full_name': 'テストユーザー',
            'username': 'test_user_001',
            'password': 'test123',
            'confirm_password': 'test123',
            'grade': '小4',
            'role': 'user'
        }
        
        print("➕ ユーザー追加中...")
        add_response = session.post(f"{base_url}/admin/users/add", data=user_data)
        
        print(f"📊 レスポンスステータス: {add_response.status_code}")
        print(f"📄 レスポンス内容: {add_response.text[:500]}...")
        
        if add_response.status_code == 302:  # リダイレクト
            print("✅ ユーザー追加リクエスト完了（リダイレクト）")
        else:
            print(f"⚠️ 予期しないレスポンス: {add_response.status_code}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    test_user_addition() 