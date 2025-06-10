import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    """ホームページが正常に表示されることをテスト"""
    response = client.get('/')
    assert response.status_code == 200

def test_login_page(client):
    """ログインページが正常に表示されることをテスト"""
    response = client.get('/login')
    assert response.status_code == 200

def test_register_page(client):
    """登録ページが正常に表示されることをテスト"""
    response = client.get('/register')
    assert response.status_code == 200 