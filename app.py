from __future__ import annotations

from pathlib import Path

import streamlit as st

from predictor import predict_from_csv_dir


st.set_page_config(page_title="nr-scope", layout="wide")

st.title("nr-scope | オッズ予想アプリ")
st.caption("nk-tracer の券種別CSVから、馬ごとの予想スコアを算出します。")

default_dir = "/home/nk-tracer/out/saudi_cup_csv"
csv_dir = st.text_input("CSVディレクトリ", value=default_dir)

run = st.button("予想を実行", type="primary")

if run:
    try:
        result = predict_from_csv_dir(csv_dir)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
    else:
        st.success("予想を生成しました")

        col1, col2 = st.columns(2)
        col1.metric("読み込みファイル数", len(result.loaded_files))
        col2.metric("対象頭数", len(result.ranking))

        with st.expander("読み込みファイル", expanded=False):
            for file_path in result.loaded_files:
                st.write(file_path)

        st.subheader("ランキング")
        st.dataframe(result.ranking, use_container_width=True, hide_index=True)

        if not result.ranking.empty:
            chart_df = result.ranking.set_index("馬名")[["予想スコア"]]
            st.subheader("予想スコア")
            st.bar_chart(chart_df)

        st.subheader("寄与内訳（上位200件）")
        if result.score_breakdown.empty:
            st.info("寄与データがありません。")
        else:
            st.dataframe(result.score_breakdown.head(200), use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("ヒント: `/home/nk-tracer/out/<race>/csv` を指定すると、取得済みCSVをそのまま分析できます。")
