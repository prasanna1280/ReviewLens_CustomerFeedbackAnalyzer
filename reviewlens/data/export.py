"""Excel-safe CSV export."""

import pandas as pd


def to_excel_csv(df: pd.DataFrame) -> bytes:
    """CSV bytes with a UTF-8 BOM so Excel shows Tamil script correctly."""
    return df.to_csv(index=False).encode("utf-8-sig")
