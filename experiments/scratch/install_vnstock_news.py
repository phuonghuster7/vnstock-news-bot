import os
import sys
import html
from vnstock_installer.api import VnstockAPIClient
from vnstock_installer.installer import VnstockInstaller

def main():
    # Buộc sys.stdout sử dụng utf-8 để tránh lỗi hiển thị tiếng Việt trên Windows console
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    api_key = os.environ.get("VNSTOCK_API_KEY")
    if not api_key:
        print("Error: VNSTOCK_API_KEY environment variable is not set.")
        sys.exit(1)
        
    python_exe = sys.executable
    print(f"Using Python: {python_exe}")
    print(f"API Key: {api_key[:10]}...")
    
    # Khởi tạo API Client
    client = VnstockAPIClient(api_key=api_key, python_executable=python_exe)
    
    # Đăng ký thiết bị với máy chủ
    print("Registering device...")
    success, msg, data = client.register_device()
    print(f"Registration status: {success} - {msg}")
    if not success:
        print("Registration failed. Cannot proceed.")
        sys.exit(1)
        
    # Khởi tạo Installer
    installer = VnstockInstaller(api_client=client, python_executable=python_exe)
    
    # Bỏ qua bước cài đặt dependencies để tránh lỗi khóa file numpy/scipy dll
    print("Skipping dependencies installation (assuming they are already satisfied)...")
    
    # Cài đặt trực tiếp gói vnstock_news
    print("Installing vnstock_news...")
    install_success, install_msg = installer.install_package("vnstock_news")
    print(f"Installation status: {install_success} - {install_msg}")
    
    if install_success:
        print("vnstock_news installed successfully!")
    else:
        print("Failed to install vnstock_news.")

if __name__ == "__main__":
    main()
