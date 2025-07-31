#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

def fix_admin_password():
    """管理者パスワードを確実にリセット"""
    db_path = 'flashcards.db'
    
    print("🔧 管理者パスワード修正開始")
    print(f"📁 データベースパス: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"❌ データベースファイルが見つかりません: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.cursor()
        
        # 1. 現在の管理者ユーザーを確認
        print("\n🔍 現在の管理者ユーザーを確認...")
        cur.execute('SELECT id, username, password_hash, is_admin, full_name FROM users WHERE username = ?', ('admin',))
        admin_user = cur.fetchone()
        
        if admin_user:
            user_id, username, password_hash, is_admin, full_name = admin_user
            print(f"👤 管理者ユーザー: ID={user_id}, ユーザー名={username}, 管理者権限={is_admin}, 表示名={full_name}")
            print(f"🔑 現在のパスワードハッシュ: {password_hash[:50]}...")
            print(f"📏 ハッシュの長さ: {len(password_hash)}")
            
            # 2. 新しいパスワードを設定
            new_password = 'admin'
            new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
            
            print(f"\n🔄 パスワードを更新...")
            print(f"新しいパスワード: {new_password}")
            print(f"新しいハッシュ: {new_hash[:50]}...")
            print(f"新しいハッシュの長さ: {len(new_hash)}")
            
            # 3. パスワードを更新
            cur.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
            
            # 4. 検証
            print(f"\n✅ パスワード更新完了")
            
            # 5. テスト用のパスワード検証
            test_result = check_password_hash(new_hash, new_password)
            print(f"パスワード検証テスト: {'✅ 成功' if test_result else '❌ 失敗'}")
            
        else:
            print("❌ 管理者ユーザーが見つかりません")
            return
        
        # 6. コミット
        conn.commit()
        print("💾 データベースコミット完了")
        
        # 7. 最終確認
        print(f"\n📊 最終確認:")
        cur.execute('SELECT id, username, is_admin FROM users WHERE username = ?', ('admin',))
        admin = cur.fetchone()
        if admin:
            print(f"✅ 管理者ユーザー: ID={admin[0]}, ユーザー名={admin[1]}, 管理者権限={admin[2]}")
        
        conn.close()
        print("\n✅ 管理者パスワード修正完了")
        print("\n📝 次のステップ:")
        print("1. 管理者ログイン: ユーザー名=admin, パスワード=admin")
        print("2. ブラウザで管理画面にアクセス")
        print("3. ユーザー追加を試してください")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")

if __name__ == "__main__":
    fix_admin_password() 