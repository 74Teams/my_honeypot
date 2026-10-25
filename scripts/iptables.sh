#!/usr/bin/env bash
# iptables.sh - NAT cổng 22/80 vào honeypot (mặc định 2222/8080) để honeypot không phải chạy root.
# Dùng:  sudo ./scripts/iptables.sh apply | remove | status
# Luật KHÔNG tồn tại qua reboot (cố ý — lab). Muốn giữ: sudo apt install iptables-persistent.
# Lưu ý: PREROUTING không áp dụng cho traffic từ chính máy này → test local thì dùng thẳng 2222/8080.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# lấy cổng từ .env nếu có
if [[ -f "$REPO_DIR/.env" ]]; then
    SSH_PORT="$(grep -E '^HONEYPY_SSH_PORT=' "$REPO_DIR/.env" | cut -d= -f2 || true)"
    HTTP_PORT="$(grep -E '^HONEYPY_HTTP_PORT=' "$REPO_DIR/.env" | cut -d= -f2 || true)"
fi
SSH_PORT="${SSH_PORT:-2222}"
HTTP_PORT="${HTTP_PORT:-8080}"
RULES=("22:$SSH_PORT" "80:$HTTP_PORT")

if [[ $EUID -ne 0 ]]; then
    echo "[!] Cần sudo." >&2
    exit 1
fi

rule() {   # rule <-A|-D|-C> <cổng ngoài> <cổng honeypot>
    iptables -t nat "$1" PREROUTING -p tcp --dport "$2" -j REDIRECT --to-port "$3"
}

case "${1:-status}" in
    apply)
        # Nếu sshd thật còn nghe cổng 22 thì sau khi NAT bạn sẽ SSH nhầm vào honeypot.
        if [[ -n "$(ss -Htln 'sport = :22')" ]]; then
            echo "[!] Vẫn có dịch vụ đang nghe cổng 22 (sshd thật?). Dời sshd sang cổng khác trước:" >&2
            echo "    sửa 'Port 22222' trong /etc/ssh/sshd_config" >&2
            echo "    sudo systemctl daemon-reload && sudo systemctl restart ssh.socket" >&2
            echo "    kiểm tra: ss -tln | grep 22222   (giữ phiên SSH hiện tại cho tới khi vào được cổng mới)" >&2
            exit 1
        fi
        for r in "${RULES[@]}"; do
            src="${r%%:*}"; dst="${r##*:}"
            if rule -C "$src" "$dst" 2>/dev/null; then
                echo "[=] $src -> $dst đã có"
            else
                rule -A "$src" "$dst" && echo "[+] $src -> $dst"
            fi
        done
        ;;
    remove)
        for r in "${RULES[@]}"; do
            src="${r%%:*}"; dst="${r##*:}"
            while rule -C "$src" "$dst" 2>/dev/null; do
                rule -D "$src" "$dst"
            done
            echo "[-] $src -> $dst"
        done
        ;;
    status)
        iptables -t nat -S PREROUTING | grep REDIRECT || echo "(chưa có luật REDIRECT nào)"
        ;;
    *)
        echo "Dùng: sudo $0 apply | remove | status" >&2
        exit 1
        ;;
esac
