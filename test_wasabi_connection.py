#!/usr/bin/env python3
"""
Wasabi接続テストスクリプト
"""

import os
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv(dotenv_path='dbname.env')

def test_wasabi_connection():
    """Wasabi接続をテスト"""
    try:
        access_key = os.getenv('WASABI_ACCESS_KEY')
        secret_key = os.getenv('WASABI_SECRET_KEY')
        endpoint = os.getenv('WASABI_ENDPOINT')
        bucket_name = os.getenv('WASABI_BUCKET')
        
        print("🔍 Wasabi設定確認:")
        print(f"  ACCESS_KEY: {'Set' if access_key else 'Not Set'}")
        print(f"  SECRET_KEY: {'Set' if secret_key else 'Not Set'}")
        print(f"  ENDPOINT: {endpoint}")
        print(f"  BUCKET: {bucket_name}")
        
        if not all([access_key, secret_key, endpoint, bucket_name]):
            print("⚠️ Wasabi設定が不完全です")
            return False
        
        print(f"🔍 Wasabi S3クライアント作成中...")
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name='us-east-1'
        )
        
        # 接続テスト
        print(f"🔍 Wasabiバケット接続テスト: {bucket_name}")
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print("✅ Wasabi接続テスト成功")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"❌ Wasabiバケット接続テスト失敗:")
            print(f"  エラーコード: {error_code}")
            print(f"  エラーメッセージ: {error_message}")
            if error_code == '403':
                print("  認証エラーまたは権限不足の可能性があります")
            elif error_code == '404':
                print("  バケットが存在しない可能性があります")
            return False
        
    except Exception as e:
        print(f"❌ Wasabi接続テストエラー: {e}")
        print(f"❌ エラータイプ: {type(e).__name__}")
        return False

if __name__ == '__main__':
    test_wasabi_connection() 