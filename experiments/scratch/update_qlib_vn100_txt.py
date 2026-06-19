import os

# Đường dẫn danh sách sạch đã lưu
clean_path = "instruments/vn100_clean.txt"
with open(clean_path, "r") as f:
    symbols = [line.strip() for line in f if line.strip()]

# Ghi đè vào qlib instruments directory
qlib_inst_dir = os.path.expanduser("~/.qlib/qlib_data/vn_data/instruments")
os.makedirs(qlib_inst_dir, exist_ok=True)

vn100_txt_path = os.path.join(qlib_inst_dir, "vn100.txt")
with open(vn100_txt_path, "w") as f:
    for sym in symbols:
        f.write(f"{sym}\t2015-01-01\t2099-12-31\n")

print(f"Đã ghi đè {len(symbols)} mã sạch vào {vn100_txt_path}")
