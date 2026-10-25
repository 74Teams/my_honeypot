"""
config.py - cấu hình tập trung cho HONEYPY.

Đọc theo thứ tự ưu tiên: biến môi trường HONEYPY_* > file .env > giá trị mặc định dưới đây.
Mọi đường dẫn mặc định tính theo thư mục chứa file này (không phụ thuộc CWD),
nên chạy từ thư mục nào trên Ubuntu hay Windows cũng ra cùng một chỗ.
"""
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HONEYPY_",
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Dữ liệu sinh ra khi chạy (DB, log, host key) nằm hết trong data/ — đã gitignore
    data_dir: Path = BASE_DIR / "data"
    db_path: Optional[Path] = None          # mặc định: data/honeypot.db
    log_dir: Optional[Path] = None          # mặc định: data/logs
    host_key_path: Optional[Path] = None    # mặc định: data/server.key (tự sinh nếu chưa có)

    bind_address: str = "0.0.0.0"

    # SSH
    ssh_port: int = 2222
    ssh_banner: str = "SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13"
    ssh_prompt: str = "corporate-jumpbox2$ "
    ssh_motd: str = "Welcome to Ubuntu 24.04.1 LTS (GNU/Linux 6.8.0-45-generic x86_64)"

    # HTTP
    http_port: int = 8080
    http_username: str = "admin"
    http_password: str = "password"

    @model_validator(mode="after")
    def _fill_paths(self):
        self.data_dir = self.data_dir.resolve()
        if self.db_path is None:
            self.db_path = self.data_dir / "honeypot.db"
        if self.log_dir is None:
            self.log_dir = self.data_dir / "logs"
        if self.host_key_path is None:
            self.host_key_path = self.data_dir / "server.key"
        return self


settings = Settings()
