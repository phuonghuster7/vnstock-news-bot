import numpy as np
import pandas as pd
from qlib.data.dataset.processor import Processor


class CSRankNorm(Processor):
    """
    Cross-sectional rank normalization.
    
    Thay vì dùng raw value (ret_5d = 0.03), 
    dùng rank trong universe tại mỗi ngày → [-1, +1]
    
    Ví dụ VN30 (30 symbols):
        rank 1/30  → score ≈ -1.0  (worst)
        rank 15/30 → score ≈  0.0  (median)
        rank 30/30 → score ≈ +1.0  (best)
    """

    def __init__(self, fields_group=None, clip_outlier=True):
        """
        fields_group: list features cần rank, None = tất cả numeric columns
        clip_outlier: clip [-3, 3] sau khi normalize (loại extreme rank)
        """
        self.fields_group = fields_group
        self.clip_outlier = clip_outlier

    def fit(self, df: pd.DataFrame):
        # Stateless processor — không cần fit
        return self

    def __call__(self, df: pd.DataFrame):
        # df index: MultiIndex (datetime, instrument)
        # df columns: feature names
        
        cols = self.fields_group if self.fields_group else df.select_dtypes("number").columns
        
        def rank_one_day(group):
            for col in cols:
                if col not in group.columns:
                    continue
                s = group[col]
                valid_mask = s.notna()
                n_valid = valid_mask.sum()
                if n_valid < 2:
                    continue
                # Percent rank → scale về [-1, +1]
                ranked = s[valid_mask].rank(pct=True)  # 0..1
                group.loc[valid_mask, col] = ranked * 2 - 1  # -1..+1
            return group

        df = df.groupby(level="datetime", group_keys=False).apply(rank_one_day)
        
        if self.clip_outlier:
            df[cols] = df[cols].clip(-3, 3)
        
        return df


if __name__ == "__main__":
    # Quick sanity check
    idx = pd.MultiIndex.from_product(
        [pd.date_range("2024-01-01", periods=3), [f"SYM{i}" for i in range(5)]],
        names=["datetime", "instrument"]
    )
    df = pd.DataFrame({"ret_5d": np.random.randn(15)}, index=idx)
    
    proc = CSRankNorm(fields_group=["ret_5d"])
    result = proc(df.copy())
    
    # Verify: mỗi ngày phải có mean ≈ 0, range [-1, +1]
    for date, group in result.groupby(level="datetime"):
        vals = group["ret_5d"].dropna()
        assert vals.min() >= -1.0 and vals.max() <= 1.0, f"Out of range: {date}"
        print(f"{date.date()}: mean={vals.mean():.3f}, min={vals.min():.3f}, max={vals.max():.3f}")
    
    print("✅ CSRankNorm OK")
