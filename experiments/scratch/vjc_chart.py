import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from vnstock import Quote

def get_aligned_price_action(symbol, exright_date, window=15):
    q = Quote(symbol=symbol)
    dt = pd.to_datetime(exright_date)
    start_date = (dt - pd.Timedelta(days=window*2 + 5)).strftime('%Y-%m-%d')
    end_date = (dt + pd.Timedelta(days=window*2 + 5)).strftime('%Y-%m-%d')
    
    try:
        df = q.history(start=start_date, end=end_date, interval="1D")
        if df is None or df.empty:
            return None
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time').reset_index(drop=True)
        
        # Find index of the ex-right date or closest date after it
        event_idx_list = df[df['time'] >= dt].index
        if len(event_idx_list) == 0:
            return None
        event_idx = event_idx_list[0]
        
        # Ensure we have enough data points on both sides
        if event_idx < window or (len(df) - event_idx) <= window:
            return None
            
        sub_df = df.iloc[event_idx - window : event_idx + window + 1].copy()
        sub_df['relative_day'] = range(-window, window + 1)
        
        # Normalize close price so that T-1 (relative_day = -1) is 100
        ref_price = sub_df[sub_df['relative_day'] == -1]['close'].values[0]
        sub_df['normalized_close'] = (sub_df['close'] / ref_price) * 100
        
        return sub_df[['relative_day', 'normalized_close']]
    except Exception as e:
        print(f"Error fetching data for date {exright_date}: {e}")
        return None

def main():
    # Pre-defined historical stock dividend dates for VJC
    dates = ["2019-10-21", "2018-09-13", "2018-05-17"]
    print("Aligning price action around historical ex-dates:", dates)
    
    plt.style.use('seaborn-v0_8-darkgrid')
    fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
    fig.patch.set_facecolor('#f8f9fa')
    ax.set_facecolor('#ffffff')
    
    colors = ['#0984e3', '#00b894', '#6c5ce7']
    color_idx = 0
    
    has_data = False
    for ex_date in dates:
        df_align = get_aligned_price_action("VJC", ex_date, window=15)
        if df_align is not None:
            label = f"Ex-date: {ex_date}"
            ax.plot(df_align['relative_day'], df_align['normalized_close'], 
                    color=colors[color_idx % len(colors)], linewidth=2.5, label=label)
            color_idx += 1
            has_data = True
            
    if not has_data:
        print("No historical data could be aligned. Creating fallback plot.")
        ax.text(0.5, 0.5, 'Không đủ dữ liệu lịch sử để căn chỉnh quanh ngày GDKHQ', 
                ha='center', va='center', fontsize=12)
    else:
        # Reference lines
        ax.axvline(x=0, color='#d63031', linestyle='--', linewidth=1.5, label='Ex-Right Date (T=0)')
        ax.axhline(y=100, color='#636e72', linestyle=':', linewidth=1)
        
        # Styling
        ax.set_title('VJC - Price Action Behavior Before & After Stock Dividend (Normalized at T-1 = 100)', 
                     fontsize=14, fontweight='bold', color='#2d3436', pad=15)
        ax.set_xlabel('Trading Days Relative to Ex-Right Date (T=0)', fontsize=11, color='#636e72')
        ax.set_ylabel('Normalized Price (%)', fontsize=11, color='#636e72')
        ax.grid(True, linestyle='--', alpha=0.5, color='#b2bec3')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#dfe6e9')
        
    plt.figtext(0.5, 0.01, 'Dữ liệu phân tích kỹ thuật - Hỗ trợ bởi vnstock', ha='center', fontsize=9, color='#94a3b8', style='italic')
    
    # Save directly to artifact path
    output_path = r"C:\Users\Admin\.gemini\antigravity-ide\brain\273e780d-9072-44f6-93e3-0328bf414e44\vjc_dividend_behavior.png"
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(output_path)
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    main()
