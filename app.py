from __future__ import annotations

import streamlit as st

from predictor import predict_from_csv_dir


st.set_page_config(page_title="nr-scope", layout="wide")

st.title("nr-scope | オッズ予想アプリ")
st.caption("同等比較できる券種ペアのみを並べて比較します。")

default_dir = "/home/nk-tracer/out/saudi_cup_csv"
csv_dir = st.text_input("CSVディレクトリ", value=default_dir)
detail_mode = st.checkbox("詳細計算モード（消し馬を除外）", value=False)
excluded_text = st.text_input("消し馬（馬番をカンマ区切り）", value="")

run = st.button("予想を実行", type="primary")

if run:
    try:
        excluded = []
        if detail_mode and excluded_text.strip():
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
        st.dataframe(result.all_market_compare, use_container_width=True, hide_index=True)

        st.subheader("比較1: 単勝 vs 馬単1着流し vs 三連単1着流し")
        st.dataframe(result.first_place_compare, use_container_width=True, hide_index=True)

        st.subheader("比較2: 単勝 vs 馬連流し vs 三連複流し")
        st.dataframe(result.flow_compare, use_container_width=True, hide_index=True)

        st.subheader("比較3: 馬連 vs 馬単裏表")
        if result.pair_compare.empty:
            st.info("馬連/馬単比較データがありません。")
        else:
            st.dataframe(result.pair_compare, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("ヒント: `/home/nk-tracer/out/<race>/csv` を指定すると、取得済みCSVをそのまま分析できます。")
