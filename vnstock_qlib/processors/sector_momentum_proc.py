"""
Sector Momentum Processor for Qlib.

Thêm 2 features cross-sectional dựa trên rotation theo ngành:
  sector_ret_5d  : return trung bình của sector trong 5 ngày
  sector_rel_ret : return của cổ phiếu - return của sector (relative strength)

Không cần data mới — dùng ret_5d đã có trong dataset.
"""

import numpy as np
import pandas as pd
from qlib.data.dataset.processor import Processor


# Sector mapping cho VN30
# Sector mapping cho VN100
SECTOR_MAP = {
    'ACB': 'bank',
    'BCG': 'construction',
    'BID': 'bank',
    'BMP': 'chemicals',
    'BSI': 'securities',
    'BVH': 'insurance',
    'CII': 'construction',
    'CMG': 'tech',
    'CTD': 'construction',
    'CTG': 'bank',
    'CTR': 'tech',
    'DBC': 'consumer',
    'DCM': 'chemicals',
    'DGC': 'chemicals',
    'DGW': 'retail',
    'DHC': 'consumer',
    'DHG': 'pharma',
    'DIG': 'realestate',
    'DPM': 'chemicals',
    'DXG': 'realestate',
    'EIB': 'bank',
    'EVF': 'bank',
    'FPT': 'tech',
    'FRT': 'retail',
    'FTS': 'securities',
    'GAS': 'utilities',
    'GEX': 'utilities',
    'GMD': 'transport',
    'GVR': 'chemicals',
    'HCM': 'securities',
    'HDB': 'bank',
    'HDC': 'realestate',
    'HDG': 'realestate',
    'HHV': 'construction',
    'HPG': 'steel',
    'HSG': 'steel',
    'IJC': 'realestate',
    'KBC': 'realestate',
    'KDC': 'consumer',
    'KDH': 'realestate',
    'LPB': 'bank',
    'MBB': 'bank',
    'MSN': 'consumer',
    'MWG': 'retail',
    'NLG': 'realestate',
    'NT2': 'utilities',
    'PAN': 'consumer',
    'PC1': 'construction',
    'PDR': 'realestate',
    'PHR': 'chemicals',
    'PLX': 'retail',
    'PNJ': 'retail',
    'POW': 'utilities',
    'PTB': 'consumer',
    'PVD': 'energy',
    'PVT': 'transport',
    'REE': 'construction',
    'SAB': 'consumer',
    'SAM': 'utilities',
    'SBT': 'consumer',
    'SCS': 'transport',
    'SHB': 'bank',
    'SJS': 'realestate',
    'SSB': 'bank',
    'SSI': 'securities',
    'STB': 'bank',
    'SZC': 'realestate',
    'TCB': 'bank',
    'TCH': 'realestate',
    'TDM': 'utilities',
    'TIP': 'realestate',
    'TPB': 'bank',
    'VCB': 'bank',
    'VCG': 'construction',
    'VCI': 'securities',
    'VGC': 'construction',
    'VHC': 'consumer',
    'VHM': 'realestate',
    'VIB': 'bank',
    'VIC': 'realestate',
    'VIX': 'securities',
    'VJC': 'transport',
    'VND': 'securities',
    'VNM': 'consumer',
    'VPB': 'bank',
    'VPI': 'realestate',
    'VRE': 'realestate',
}

DEFAULT_SECTOR = "other"


class SectorMomentumProcessor(Processor):
    """
    Cross-sectional Sector Momentum Processor.

    Dựa trên ret_5d (hoặc feature_col được chỉ định), tính:
      sector_ret_5d  = mean(ret_5d) của tất cả cổ phiếu cùng ngành trong cùng ngày
      sector_rel_ret = ret_5d của cổ phiếu - sector_ret_5d (relative strength)

    Cả hai features được thêm vào DataFrame sau khi xử lý.
    """

    def __init__(self, feature_col: str = "ret_5d"):
        """
        feature_col: tên cột momentum base (phải tồn tại trong DataFrame sau normalization).
        """
        self.feature_col = feature_col

    def fit(self, df: pd.DataFrame):
        # Stateless processor
        return self

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame:
        # Check if feature_col exists in the column levels
        has_col = False
        target_col = self.feature_col
        if isinstance(df.columns, pd.MultiIndex):
            for col in df.columns:
                if col[1] == self.feature_col:
                    has_col = True
                    target_col = col
                    break
        else:
            if self.feature_col in df.columns:
                has_col = True

        if not has_col:
            return df

        df = df.copy()
        
        # Get sector mapped values
        instruments = df.index.get_level_values("instrument")
        sectors = [SECTOR_MAP.get(sym, DEFAULT_SECTOR) for sym in instruments]
        df["_sector"] = sectors

        # Calculate sector average return cross-sectionally
        series_to_mean = df[target_col]
        sector_avg = series_to_mean.groupby([df.index.get_level_values("datetime"), df["_sector"]]).transform("mean")
        
        # Calculate market breadth (fraction of stocks with positive return) per day
        # Look for ret_1d to calculate breadth
        ret_1d_col = None
        if isinstance(df.columns, pd.MultiIndex):
            for col in df.columns:
                if col[1] == "ret_1d":
                    ret_1d_col = col
                    break
        else:
            if "ret_1d" in df.columns:
                ret_1d_col = "ret_1d"

        if ret_1d_col is not None:
            # Breadth is the percentage of stocks with positive ret_1d each day
            pos_ret = (df[ret_1d_col] > 0).astype(float)
            breadth = pos_ret.groupby(level="datetime").transform("mean")
            # If breadth > 70% VN30 stocks, weight is 0.2, else 1.0
            weight = np.where(breadth > 0.7, 0.2, 1.0)
        else:
            weight = 1.0

        # Apply adaptive weight to sector average and relative strength
        sector_avg_weighted = sector_avg * weight
        sector_rel_weighted = (series_to_mean - sector_avg) * weight

        # Drop temporary sector column before adding features to maintain index symmetry
        df = df.drop(columns=["_sector"])

        # Insert new columns
        if isinstance(df.columns, pd.MultiIndex):
            # Find the group of the target_col
            group_name = target_col[0]
            
            # Extract underlying arrays to append columns dynamically without index mismatches
            df[(group_name, "sector_ret_5d")] = sector_avg_weighted.values
            df[(group_name, "sector_rel_ret")] = sector_rel_weighted.values
        else:
            df["sector_ret_5d"] = sector_avg_weighted
            df["sector_rel_ret"] = sector_rel_weighted
            
        return df






if __name__ == "__main__":
    # Quick sanity check
    idx = pd.MultiIndex.from_tuples([
        (pd.Timestamp("2024-01-02"), "VCB"),
        (pd.Timestamp("2024-01-02"), "BID"),
        (pd.Timestamp("2024-01-02"), "FPT"),
        (pd.Timestamp("2024-01-03"), "VCB"),
        (pd.Timestamp("2024-01-03"), "FPT"),
    ], names=["datetime", "instrument"])

    df = pd.DataFrame({
        "ret_5d": [0.05, 0.03, -0.02, 0.01, 0.04],
        "log_vol": [1.0, 1.1, 0.9, 1.2, 0.8],
    }, index=idx)

    proc = SectorMomentumProcessor(feature_col="ret_5d")
    result = proc(df)
    print(result[["ret_5d", "sector_ret_5d", "sector_rel_ret"]])
    # VCB & BID (bank): sector_ret_5d = mean(0.05, 0.03) = 0.04
    # FPT (tech):       sector_ret_5d = -0.02
    assert abs(result.loc[(pd.Timestamp("2024-01-02"), "VCB"), "sector_ret_5d"] - 0.04) < 1e-6
    print("✅ SectorMomentumProcessor OK")
