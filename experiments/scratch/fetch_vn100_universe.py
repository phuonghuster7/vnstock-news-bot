from vnstock import Listing, Quote
import pandas as pd
import os

def fetch_vn100():
    listing = Listing()
    try:
        print("Đang lấy danh sách VN100...")
        all_symbols = listing.all_symbols()
        vn100 = listing.symbols_by_index("VN100")
        symbols = vn100["symbol"].tolist()
    except Exception as e:
        print("Lỗi lấy VN100 trực tiếp:", e)
        # Fallback
        try:
            print("Fallback: Thử lấy danh sách all symbols và lọc...")
            df_symbols = listing.all_symbols()
            hose = df_symbols[df_symbols["exchange"] == "HOSE"]
            symbols = hose["symbol"].head(100).tolist()
        except Exception as e2:
            print("Lỗi fallback:", e2)
            # Hardcode list VN100 thực tế nếu API lỗi
            symbols = [
                "ACB", "BCG", "BID", "BMP", "BSI", "BVH", "CII", "CMG", "CTD", "CTG",
                "CTR", "DBC", "DCM", "DGC", "DGW", "DHC", "DHG", "DIG", "DPC", "DPM",
                "DXG", "EIB", "EVF", "FPT", "FRT", "FTS", "GAS", "GEX", "GMD", "GVR",
                "HCM", "HDB", "HDC", "HDG", "HHV", "HPG", "HSG", "IJC", "KBC", "KDC",
                "KDH", "LPB", "MBB", "MSN", "MWG", "NLG", "NT2", "OCB", "PAN", "PC1",
                "PDR", "PHR", "PLX", "PNJ", "POW", "PTB", "PVD", "PVT", "REE", "SAB",
                "SAM", "SBT", "SCS", "SHB", "SJS", "SSB", "SSI", "STB", "SZC", "TCB",
                "TCH", "TDM", "TIP", "TPB", "VCB", "VCG", "VCI", "VGC", "VHC", "VHM",
                "VIB", "VIC", "VIX", "VJC", "VND", "VNM", "VPB", "VPI", "VRE"
            ]
            
    print(f"Tổng số mã VN100: {len(symbols)}")
    print(symbols)
    return symbols

def check_data_coverage(symbols: list, start="2018-01-01"):
    import time
    coverage = []
    print(f"Đang kiểm tra data coverage cho {len(symbols)} mã từ {start}...")
    for idx, sym in enumerate(symbols):
        print(f"[{idx+1}/{len(symbols)}] Đang kiểm tra mã {sym}...")
        df = None
        retries = 3
        while retries > 0:
            try:
                for src in ["kbs", "vci"]:
                    try:
                        df = Quote(symbol=sym, source=src).history(
                            start=start, end="2024-12-31", interval="1D"
                        )
                        if df is not None and len(df) > 0:
                            break
                    except Exception as e_src:
                        # Thư viện vnstock có thể in ra terminal rồi tự động raise hoặc exit.
                        # Ta sẽ bắt Exception và kiểm tra chuỗi lỗi rộng hơn.
                        err_str = str(e_src).lower()
                        if "rate limit" in err_str or "giới hạn" in err_str or "exceeded" in err_str:
                            raise e_src
                        continue
                    except BaseException as e_base:
                        # Bắt cả SystemExit hoặc KeyboardInterrupt/BaseException khác nếu vnstock gọi sys.exit()
                        err_str = str(e_base).lower()
                        if "rate limit" in err_str or "giới hạn" in err_str or "exceeded" in err_str or len(err_str) == 0:
                            # Nếu vnstock crash/sys.exit không có message cụ thể
                            raise Exception("Rate Limit Exceeded via BaseException")
                        raise e_base
                
                if df is not None and len(df) > 0:
                    coverage.append({
                        "symbol":     sym,
                        "rows":       len(df),
                        "start_date": df.index.min() if hasattr(df, "index") else "N/A",
                        "end_date":   df.index.max() if hasattr(df, "index") else "N/A",
                        "ok":         len(df) > 1000,
                    })
                else:
                    coverage.append({"symbol": sym, "rows": 0, "ok": False, "error": "No data fetched"})
                break # Thành công, thoát vòng lặp retry
            except Exception as e:
                err_str = str(e).lower()
                if "rate limit" in err_str or "giới hạn" in err_str or "exceeded" in err_str:
                    print("⚠️ Gặp Rate Limit. Đang sleep 35 giây để reset...")
                    time.sleep(35)
                    retries -= 1
                else:
                    coverage.append({"symbol": sym, "rows": 0, "ok": False, "error": str(e)})
                    break
            except BaseException as e_base:
                err_str = str(e_base).lower()
                if "rate limit" in err_str or "giới hạn" in err_str or "exceeded" in err_str or len(err_str) == 0:
                    print("⚠️ Gặp Rate Limit (BaseException). Đang sleep 35 giây để reset...")
                    time.sleep(35)
                    retries -= 1
                else:
                    coverage.append({"symbol": sym, "rows": 0, "ok": False, "error": str(e_base)})
                    break
        
        # Sleep nhẹ 0.5s giữa các mã để tránh trigger rate limit
        time.sleep(0.5)
            
    df_cov = pd.DataFrame(coverage)
    clean_symbols = df_cov[df_cov["ok"]]["symbol"].tolist()
    
    print(f"\nMã có đủ data (>1000 rows): {len(clean_symbols)}/{len(symbols)}")
    print(f"Mã thiếu data: {df_cov[~df_cov['ok']]['symbol'].tolist()}")
    
    os.makedirs("instruments", exist_ok=True)
    with open("instruments/vn100_clean.txt", "w") as f:
        f.write("\n".join(clean_symbols))
    print("Đã lưu instruments/vn100_clean.txt")
    return clean_symbols

if __name__ == "__main__":
    syms = fetch_vn100()
    check_data_coverage(syms)
