import event_store
from config import settings


def test_log_event_roundtrip():
    event_store.log_event('ssh', 'auth_attempt', '192.168.56.102', username='root', password='toor')
    event_store.log_event('http', 'http_login', '192.168.56.102', username="' OR 1=1--",
                          password='x', user_agent='sqlmap/1.8', attack_tag='sqli')

    rows = event_store.query("SELECT * FROM events ORDER BY id")
    assert [r['event_type'] for r in rows] == ['auth_attempt', 'http_login']
    assert rows[0]['username'] == 'root' and rows[0]['password'] == 'toor'
    assert rows[1]['attack_tag'] == 'sqli'
    assert rows[1]['user_agent'] == 'sqlmap/1.8'


def test_db_created_under_data_dir():
    event_store.init_db()
    assert settings.db_path.exists()


def test_query_uses_parameters_not_string_concat():
    payload = "x'); DROP TABLE events;--"
    event_store.log_event('ssh', 'command', '10.0.0.1', command=payload)
    rows = event_store.query("SELECT command FROM events WHERE command = ?", (payload,))
    assert rows == [{'command': payload}]


def test_log_event_never_raises(monkeypatch, tmp_path):
    # db_path trỏ vào một thư mục → sqlite không mở được; honeypot vẫn không được sập
    bad = tmp_path / "is_a_dir"
    bad.mkdir()
    monkeypatch.setattr(settings, "db_path", bad)
    event_store.log_event('ssh', 'auth_attempt', '10.0.0.1')
