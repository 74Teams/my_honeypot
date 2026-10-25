#!/usr/bin/env bash
# setup_ubuntu.sh - cài HONEYPY trên Ubuntu VM sau khi git clone / git pull.
# Dùng:  ./scripts/setup_ubuntu.sh          (KHÔNG cần sudo; script tự gọi sudo cho apt)
# Chạy lại nhiều lần vẫn an toàn.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [[ $EUID -eq 0 ]]; then
    echo "[!] Đừng chạy bằng root — honeypot phải chạy bằng user thường." >&2
    exit 1
fi

echo "[*] Cài gói hệ thống..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git iptables

echo "[*] Tạo virtualenv .venv ..."
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements-dev.txt

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "[*] Đã tạo .env từ .env.example"
fi

mkdir -p data
chmod 700 data
chmod +x scripts/*.sh

echo "[*] Chạy test..."
.venv/bin/python -m pytest -q

cat <<EOF

[+] Xong. Các bước tiếp theo:
    source .venv/bin/activate
    python3 honeypy.py --ssh            # cổng 2222 (host key tự sinh trong data/)
    python3 honeypy.py --http           # cổng 8080
    uvicorn api:app --host 127.0.0.1 --port 8000

    Muốn Kali tấn công vào cổng chuẩn 22/80: dời sshd thật sang cổng khác
    rồi chạy  sudo ./scripts/iptables.sh apply   (xem CLAUDE.md mục 1)
EOF
