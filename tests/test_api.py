from fastapi.testclient import TestClient

import event_store
from api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_events_and_bruteforce():
    for pw in ["123456", "password", "toor", "admin", "root"]:
        event_store.log_event('ssh', 'auth_attempt', '192.168.56.102', username='root', password=pw)
    event_store.log_event('ssh', 'auth_attempt', '192.168.56.103', username='root', password='x')

    events = client.get("/events", params={"src_ip": "192.168.56.102"}).json()
    assert len(events) == 5

    brute = client.get("/stats/bruteforce", params={"threshold": 5}).json()
    assert [b["src_ip"] for b in brute] == ["192.168.56.102"]
    assert brute[0]["distinct_passwords"] == 5
