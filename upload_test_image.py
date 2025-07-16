#!/usr/bin/env python3
"""
テスト用画像をWasabiにアップロードするスクリプト
"""

import os
import boto3
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv(dotenv_path='dbname.env')

def create_test_image(filename, text="テスト画像"):
    """テスト用画像を作成"""
    # 300x200の画像を作成
    img = Image.new('RGB', (300, 200), color='lightblue')
    draw = ImageDraw.Draw(img)
    
    # テキストを描画
    try:
        # 日本語フォントを試行
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    # テキストを中央に配置
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (300 - text_width) // 2
    y = (200 - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=font)
    
    # 画像を保存
    img.save(filename)
    print(f"✅ テスト画像を作成: {filename}")

def upload_test_images():
    """テスト用画像をWasabiにアップロード"""
    try:
        # Wasabiクライアントを初期化
        access_key = os.getenv('WASABI_ACCESS_KEY')
        secret_key = os.getenv('WASABI_SECRET_KEY')
        endpoint = os.getenv('WASABI_ENDPOINT')
        bucket_name = os.getenv('WASABI_BUCKET')
        
        if not all([access_key, secret_key, endpoint, bucket_name]):
            print("❌ Wasabi設定が不完全です")
            return
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name='ap-northeast-1'
        )
        
        # テスト用画像を作成
        test_images = [
            ("1-2.png", "テスト画像 1-2"),
            ("2-1.png", "テスト画像 2-1"),
            ("3-1.png", "テスト画像 3-1"),
        ]
        
        folder_path = "社会/ファイナルステージ/地理"
        
        for filename, text in test_images:
            # 画像を作成
            create_test_image(filename, text)
            
            # Wasabiにアップロード
            try:
                image_key = f"{folder_path}/{filename}"
                s3_client.upload_file(
                    filename,
                    bucket_name,
                    image_key,
                    ExtraArgs={
                        'ContentType': 'image/png',
                        'ACL': 'public-read'
                    }
                )
                print(f"✅ 画像をアップロード: {image_key}")
                
                # ローカルファイルを削除
                os.remove(filename)
                
            except Exception as e:
                print(f"❌ アップロードエラー {filename}: {e}")
        
        print("🎉 テスト画像のアップロードが完了しました")
        
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == '__main__':
    upload_test_images() 