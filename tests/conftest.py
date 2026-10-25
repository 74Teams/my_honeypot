import pytest

from config import settings


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    """Mỗi test dùng data/ riêng trong thư mục tạm, không đụng vào DB thật."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "db_path", tmp_path / "honeypot.db")
    monkeypatch.setattr(settings, "log_dir", tmp_path / "logs")
    monkeypatch.setattr(settings, "host_key_path", tmp_path / "server.key")
    return tmp_path
