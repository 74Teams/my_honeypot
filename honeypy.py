import argparse #là thư viện xây dựng sẵn của Python dùng để xử lý các tham số dòng lệnh
'''
Nó giúp bạn truyền dữ liệu vào chương trình ngay khi chạy lệnh trên Terminal/Command Prompt (ví dụ: python main.py -a 127.0.0.1 -p 8080 --ssh), thay vì phải sửa code hoặc nhập dữ liệu thủ công bằng hàm input() khi chương trình đang chạy.'''
from ssh_honeypot import *
from web_honeypot import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser() # đối tượng quản lý các tham số đầu vào

    # Định nghĩa các tham số bắt buộc phải truyền vào (-a: Địa chỉ IP, -p: Cổng kết nối)
    parser.add_argument('-a', '--address', type=str, required=True)
    parser.add_argument('-p', '--port', type=int, required=True)
    parser.add_argument('-u', '--username', type=str)
    parser.add_argument('-pw', '--password', type=str)

    parser.add_argument('-s', '--ssh', action="store_true")
    parser.add_argument('-w', '--http', action="store_true")

    args = parser.parse_args() # phan tích cú pháp người dùng nhập vào và lưu vào  biến args

    try:
        #nếu mà truyền vào -s
        if args.ssh:
            print("[-] Running SSH Honeypot...")
            # Gọi hàm honeypot() từ thư viện ssh_honeypot để chạy SSH bẫy
            honeypot(args.address, args.port, args.username, args.password)

        # nếu mà truyền vào -w
        elif args.http:
            print("[-] Running HTTP WordPress Honeypot...")
            # Nếu không truyền username/password thì mặc định là admin/password
            if not args.username:
                args.username = "admin"
            if not args.password:
                args.password = "password"

            # In ra màn hình cấu hình hiện tại của Web Honeypot
            print(f'Address: {args.address} Port: {args.port} '
                  f'Username: {args.username} Password: {args.password}')

            # Gọi hàm run_web_honeypot() từ thư viện web_honeypot để chạy Web bẫy giả lập WordPress
            run_web_honeypot(host=args.address, port=args.port,
                              input_username=args.username,
                              input_password=args.password)

        # Trường hợp 3: Người dùng nhập IP/Port nhưng quên không chọn loại -s hay -w
        else:
            print("[!] Choose a honeypot type (SSH --ssh) or (HTTP --http).")
    # Xử lý ngoại lệ (Exception) khi người dùng bấm Ctrl + C trên bàn phím để dừng chương trình
    except KeyboardInterrupt:
        print("\n Exiting HONEYPY...")