from __future__ import annotations

import streamlit as st
import pandas as pd

from predictor import predict_from_csv_dir


def _style_compare_table(df: pd.DataFrame, odds_columns: list[str]):
    def style_row(row: pd.Series):
        numeric_values: dict[str, float] = {}
        for col in odds_columns:
            value = pd.to_numeric(row.get(col), errors="coerce")
            if pd.notna(value):
                numeric_values[col] = float(value)

        styles = ["" for _ in row.index]
        if not numeric_values:
            return styles

        high_col = max(numeric_values, key=numeric_values.get)
        low_col = min(numeric_values, key=numeric_values.get)

        for idx, col in enumerate(row.index):
            if col == high_col:
                styles[idx] = "background-color: #fff4cc; font-weight: 700;"
            elif col == low_col:
                styles[idx] = "color: #9ca3af;"
        return styles

    return df.style.apply(style_row, axis=1)


def _sorted_by_spread(df: pd.DataFrame) -> pd.DataFrame:
    if "差異幅" not in df.columns:
        return df
    return df.sort_values(by=["差異幅", "馬番"], ascending=[False, True], na_position="last").reset_index(drop=True)


st.set_page_config(page_title="nr-scope", layout="wide")

st.title("nr-scope | オッズ予想アプリ")
st.caption("同等比較できる券種ペアのみを並べて比較します。")

default_dir = "/home/nk-tracer/out/saudi_cup_csv"
csv_dir = st.text_input("CSVディレクトリ", value=default_dir)
excluded_text = st.text_input("消し馬（馬番をカンマ区切り）", value="")

run = st.button("予想を実行", type="primary")

if run:
    try:
        excluded = [item.strip() for item in excluded_text.split(",") if item.strip()]
        result = predict_from_csv_dir(csv_dir, excluded_horses=excluded)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
    else:
        st.success("合成オッズを計算しました")

        col1, col2 = st.columns(2)
        col1.metric("読み込みファイル数", len(result.loaded_files))
        col2.metric("対象頭数", len(result.first_place_compare))

        if result.excluded_horses:
            st.info(f"除外中の馬番: {', '.join(result.excluded_horses)}")

        with st.expander("読み込みファイル", expanded=False):
            for file_path in result.loaded_files:
                st.write(file_path)

        st.subheader("全券種比較テーブル（全馬）")
        all_market_view = result.all_market_compare.drop(columns=["差異幅"], errors="ignore")
        st.dataframe(all_market_view, use_container_width=True, hide_index=True)

        st.subheader("比較1: 単勝 vs 馬単1着流し vs 三連単1着流し")
        first_sort = st.checkbox("比較1を差異幅でソート", value=True)
        first_view = _sorted_by_spread(result.first_place_compare) if first_sort else result.first_place_compare
        first_odds_cols = ["単勝オッズ", "馬単(1着流し)合成オッズ", "三連単(1着流し)合成オッズ"]
        st.dataframe(_style_compare_table(first_view, first_odds_cols), use_container_width=True, hide_index=True)

        st.subheader("比較2: 複勝 vs 三連複流し")
        flow_sort = st.checkbox("比較2を差異幅でソート", value=True)
        flow_view = _sorted_by_spread(result.flow_compare) if flow_sort else result.flow_compare
        flow_odds_cols = ["複勝オッズ", "三連複流し合成オッズ"]
        st.dataframe(_style_compare_table(flow_view, flow_odds_cols), use_container_width=True, hide_index=True)

        st.subheader("比較3: 馬連 vs 馬単裏表")
        if result.pair_compare.empty:
            st.info("馬連/馬単比較データがありません。")
        else:
            pair_sort = st.checkbox("比較3を差異幅でソート", value=True)
            pair_view = result.pair_compare
            if pair_sort and "差異幅" in pair_view.columns:
                pair_view = pair_view.sort_values(by=["差異幅", "馬番A", "馬番B"], ascending=[False, True, True]).reset_index(drop=True)
            pair_odds_cols = ["馬連オッズ", "馬単表裏合成オッズ"]
            st.dataframe(_style_compare_table(pair_view, pair_odds_cols), use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("ヒント: `/home/nk-tracer/out/<race>/csv` を指定すると、取得済みCSVをそのまま分析できます。")
