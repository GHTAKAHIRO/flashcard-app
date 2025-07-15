import os
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv(dotenv_path='dbname.env')

def check_wasabi_config():
    """Wasabi設定を確認"""
    print("🔍 Wasabi設定チェック:")
    print(f"WASABI_ACCESS_KEY: {'Set' if os.getenv('WASABI_ACCESS_KEY') else 'Not set'}")
    print(f"WASABI_SECRET_KEY: {'Set' if os.getenv('WASABI_SECRET_KEY') else 'Not set'}")
    print(f"WASABI_BUCKET: {os.getenv('WASABI_BUCKET', 'Not set')}")
    print(f"WASABI_ENDPOINT: {os.getenv('WASABI_ENDPOINT', 'Not set')}")
    print(f"WASABI_FOLDER_PATH: {os.getenv('WASABI_FOLDER_PATH', 'question_images (default)')}")
    
    print("\n📁 画像保存パス例:")
    folder_path = os.getenv('WASABI_FOLDER_PATH', 'question_images')
    print(f"問題ID 123の画像: {folder_path}/123/[uuid].jpg")
    print(f"問題ID 456の画像: {folder_path}/456/[uuid].png")
    
    print("\n⚠️ 注意事項:")
    if not all([os.getenv('WASABI_ACCESS_KEY'), os.getenv('WASABI_SECRET_KEY'), 
                os.getenv('WASABI_BUCKET'), os.getenv('WASABI_ENDPOINT')]):
        print("- Wasabi設定が不完全です。画像アップロード機能は無効になります。")
        print("- 環境変数ファイル（dbname.env）にWasabi設定を追加してください。")
    else:
        print("- Wasabi設定は完了しています。")
        print("- 画像アップロード機能が利用可能です。")

if __name__ == "__main__":
    check_wasabi_config() 