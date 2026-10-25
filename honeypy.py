import argparse #là thư viện xây dựng sẵn của Python dùng để xử lý các tham số dòng lệnh
'''
Nó giúp bạn truyền dữ liệu vào chương trình ngay khi chạy lệnh trên Terminal/Command Prompt (ví dụ: python3 honeypy.py -a 0.0.0.0 -p 2222 --ssh), thay vì phải sửa code hoặc nhập dữ liệu thủ công bằng hàm input() khi chương trình đang chạy.
Tham số nào không truyền thì lấy mặc định từ config.py / file .env.'''
from config import settings
from ssh_honeypot import honeypot
from web_honeypot import run_web_honeypot

if __name__ == "__main__":
    parser = argparse.ArgumentParser() # đối tượng quản lý các tham số đầu vào

    # -a: Địa chỉ IP, -p: Cổng kết nối (mặc định theo loại honeypot: ssh_port / http_port)
    parser.add_argument('-a', '--address', type=str, default=settings.bind_address)
    parser.add_argument('-p', '--port', type=int)
    parser.add_argument('-u', '--username', type=str)
    parser.add_argument('-pw', '--password', type=str)

    parser.add_argument('-s', '--ssh', action="store_true")
    parser.add_argument('-w', '--http', action="store_true")

    args = parser.parse_args() # phan tích cú pháp người dùng nhập vào và lưu vào  biến args

    try:
        #nếu mà truyền vào -s
        if args.ssh:
            port = args.port or settings.ssh_port
            print(f"[-] Running SSH Honeypot on {args.address}:{port}...")
            # Không truyền username/password thì honeypot chấp nhận mọi mật khẩu
            honeypot(args.address, port, args.username, args.password)

        # nếu mà truyền vào -w
        elif args.http:
            port = args.port or settings.http_port
            # Nếu không truyền username/password thì lấy từ config (mặc định admin/password)
            username = args.username or settings.http_username
            password = args.password or settings.http_password
            print("[-] Running HTTP WordPress Honeypot...")
            print(f'Address: {args.address} Port: {port} '
                  f'Username: {username} Password: {password}')

            # Gọi hàm run_web_honeypot() từ thư viện web_honeypot để chạy Web bẫy giả lập WordPress
            run_web_honeypot(host=args.address, port=port,
                             input_username=username,
                             input_password=password)

        # Trường hợp 3: Người dùng quên không chọn loại -s hay -w
        else:
            print("[!] Choose a honeypot type (SSH --ssh) or (HTTP --http).")
    # Xử lý ngoại lệ (Exception) khi người dùng bấm Ctrl + C trên bàn phím để dừng chương trình
    except KeyboardInterrupt:
        print("\n Exiting HONEYPY...")
