import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

print("🔧 データベース直接修正開始")

try:
    # データベース接続
    conn = sqlite3.connect('flashcards.db')
    cursor = conn.cursor()
    
    print("✅ データベース接続成功")
    
    # 1. 管理者パスワード修正
    print("\n🔑 管理者パスワード修正中...")
    cursor.execute('SELECT id, username, password_hash FROM users WHERE username = ?', ('admin',))
    admin = cursor.fetchone()
    
    if admin:
        user_id, username, current_hash = admin
        print(f"管理者ユーザー: ID={user_id}, ユーザー名={username}")
        
        # 新しいパスワードハッシュを生成
        new_password = 'admin'
        new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        # パスワードを更新
        cursor.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, 'admin'))
        conn.commit()
        
        print("✅ 管理者パスワード更新完了")
        print("ユーザー名: admin")
        print("パスワード: admin")
    else:
        print("❌ 管理者ユーザーが見つかりません")
    
    # 2. assignment_typeカラム修正
    print("\n🔧 assignment_typeカラム修正中...")
    cursor.execute("PRAGMA table_info(textbook_assignments)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'assignment_type' not in column_names:
        print("assignment_typeカラムを追加中...")
        cursor.execute("ALTER TABLE textbook_assignments ADD COLUMN assignment_type TEXT")
        
        if 'study_type' in column_names:
            cursor.execute("UPDATE textbook_assignments SET assignment_type = study_type WHERE assignment_type IS NULL")
            print("既存データをstudy_typeからコピーしました")
        
        conn.commit()
        print("✅ assignment_typeカラム追加完了")
    else:
        print("✅ assignment_typeカラムは既に存在します")
    
    # 3. データベース状態確認
    print("\n📊 データベース状態確認...")
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    print(f"ユーザー数: {user_count}")
    
    cursor.execute("SELECT COUNT(*) FROM textbook_assignments")
    assignment_count = cursor.fetchone()[0]
    print(f"テキストブック割り当て数: {assignment_count}")
    
    # 最新のユーザーを確認
    cursor.execute("""
        SELECT id, username, full_name, is_admin, created_at 
        FROM users 
        ORDER BY id DESC 
        LIMIT 3
    """)
    recent_users = cursor.fetchall()
    print("最新のユーザー（上位3件）:")
    for user in recent_users:
        print(f"  ID: {user[0]}, ユーザー名: {user[1]}, 表示名: {user[2]}, 管理者: {user[3]}, 作成日: {user[4]}")
    
    conn.close()
    print("\n✅ データベース修正完了")
    print("\n📝 次のステップ:")
    print("1. Renderでアプリケーションを再起動してください")
    print("2. 管理者ログインをテストしてください（ユーザー名: admin, パスワード: admin）")
    print("3. ユーザー登録をテストしてください")
    
except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    print(f"詳細エラー: {traceback.format_exc()}") 