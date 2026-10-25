import importlib
import os

import paramiko

from config import BASE_DIR, Settings, settings


def test_default_paths_are_absolute_and_inside_repo(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                       # CWD khác repo vẫn ra cùng đường dẫn
    for key in list(os.environ):
        if key.startswith('HONEYPY_'):
            monkeypatch.delenv(key)
    s = Settings(_env_file=None)
    assert s.db_path == BASE_DIR / "data" / "honeypot.db"
    assert s.host_key_path == BASE_DIR / "data" / "server.key"
    assert s.db_path.is_absolute()


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("HONEYPY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HONEYPY_SSH_PORT", "2022")
    s = Settings(_env_file=None)
    assert s.ssh_port == 2022
    assert s.db_path == tmp_path.resolve() / "honeypot.db"


def test_importing_sensors_has_no_side_effects():
    # trước đây import ssh_honeypot sẽ crash nếu thiếu server.key
    import ssh_honeypot, web_honeypot
    importlib.reload(ssh_honeypot)
    importlib.reload(web_honeypot)
    assert not settings.host_key_path.exists()
    assert not settings.log_dir.exists()


def test_host_key_generated_once():
    from ssh_honeypot import load_host_key
    k1 = load_host_key()
    assert settings.host_key_path.exists()
    k2 = load_host_key()
    assert isinstance(k1, paramiko.RSAKey)
    assert k1.get_fingerprint() == k2.get_fingerprint()
