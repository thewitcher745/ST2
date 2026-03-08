from pandas import DataFrame, Series


def convert_pivot_to_kline(
    pivot_index: int, zigzag_df: DataFrame, klines_df: DataFrame
) -> Series:
    """
    Converts a pivot index from zigzag_df to its corresponding kline index
    """
    return klines_df.iloc[zigzag_df.iloc[pivot_index].kline_index]

