from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


BET_TYPES = ["単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "三連複", "三連単"]


@dataclass
class PredictionResult:
    all_market_compare: pd.DataFrame
    first_place_compare: pd.DataFrame
    flow_compare: pd.DataFrame
    pair_compare: pd.DataFrame
    loaded_files: list[str]
    excluded_horses: list[str]


def _parse_odds_value(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    text = text.replace(",", "")
    text = text.replace("〜", "-")
    if "-" in text:
        parts = [part.strip() for part in text.split("-") if part.strip()]
        values: list[float] = []
        for part in parts:
            try:
                values.append(float(part))
            except ValueError:
                continue
        if not values:
            return None
        return sum(values) / len(values)
    try:
        return float(text)
    except ValueError:
        return None


def _load_csv_map(csv_dir: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    frames: dict[str, pd.DataFrame] = {}
    loaded_files: list[str] = []
    for bet_type in BET_TYPES:
        file_path = csv_dir / f"{bet_type}.csv"
        if not file_path.exists() or file_path.stat().st_size == 0:
            continue
        frame = pd.read_csv(file_path)
        if frame.empty:
            continue
        frames[bet_type] = frame
        loaded_files.append(str(file_path))
    return frames, loaded_files


def _combo_numbers(combo: object) -> list[str]:
    text = str(combo).strip()
    if not text:
        return []
    return [p.strip() for p in text.split("-") if p.strip()]


def _synthetic_odds(odds_list: list[float]) -> float | None:
    probs = [1.0 / odd for odd in odds_list if odd and odd > 0]
    total = sum(probs)
    if total <= 0:
        return None
    return 1.0 / total


def _horse_sort_key(horse_no: str) -> int:
    return int(horse_no) if horse_no.isdigit() else 9999


def _build_horse_master(tansho: pd.DataFrame, excluded: set[str]) -> pd.DataFrame:
    if not {"馬番", "馬名", "オッズ"}.issubset(set(tansho.columns)):
        raise ValueError("単勝.csv に必要な列（馬番, 馬名, オッズ）がありません。")

    rows: list[dict[str, object]] = []
    for _, row in tansho.iterrows():
        horse_no = str(row.get("馬番", "")).strip()
        if not horse_no or horse_no in excluded:
            continue
        rows.append(
            {
                "馬番": horse_no,
                "馬名": str(row.get("馬名", "")).strip(),
                "単勝オッズ": _parse_odds_value(row.get("オッズ")),
            }
        )

    master = pd.DataFrame(rows).drop_duplicates(subset=["馬番"], keep="first")
    if master.empty:
        raise ValueError("有効な馬データがありません（消し馬設定を確認してください）。")
    master["馬番_num"] = pd.to_numeric(master["馬番"], errors="coerce")
    master = master.sort_values(by=["馬番_num"]).reset_index(drop=True)
    return master


def _collect_horse_flow_odds(
    frame: pd.DataFrame,
    horses: list[str],
    excluded: set[str],
    mode: str,
    position: int | None = None,
) -> dict[str, float | None]:
    data: dict[str, list[float]] = {h: [] for h in horses}
    if frame is None or frame.empty or not {"組み合わせ", "オッズ"}.issubset(set(frame.columns)):
        return {h: None for h in horses}

    for _, row in frame.iterrows():
        combo = _combo_numbers(row.get("組み合わせ"))
        if not combo or any(item in excluded for item in combo):
            continue
        odd = _parse_odds_value(row.get("オッズ"))
        if odd is None or odd <= 0:
            continue

        targets: list[str] = []
        if mode == "contains":
            targets = [h for h in combo if h in data]
        elif mode == "position" and position is not None:
            if len(combo) > position and combo[position] in data:
                targets = [combo[position]]

        for horse_no in targets:
            data[horse_no].append(odd)

    return {horse_no: _synthetic_odds(odds_list) for horse_no, odds_list in data.items()}


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if _horse_sort_key(a) <= _horse_sort_key(b) else (b, a)


def _add_spread_column(df: pd.DataFrame, odds_columns: list[str], column_name: str = "差異幅") -> pd.DataFrame:
    frame = df.copy()
    if frame.empty:
        frame[column_name] = []
        return frame

    numeric = frame[odds_columns].apply(pd.to_numeric, errors="coerce")
    frame[column_name] = (numeric.max(axis=1) - numeric.min(axis=1)).round(4)
    return frame


def _build_pair_compare(
    umaren: pd.DataFrame | None,
    umatan: pd.DataFrame | None,
    horse_name_map: dict[str, str],
    excluded: set[str],
) -> pd.DataFrame:
    umaren_map: dict[tuple[str, str], float] = {}
    if umaren is not None and not umaren.empty and {"組み合わせ", "オッズ"}.issubset(set(umaren.columns)):
        for _, row in umaren.iterrows():
            nums = _combo_numbers(row.get("組み合わせ"))
            if len(nums) != 2:
                continue
            if any(n in excluded for n in nums):
                continue
            odd = _parse_odds_value(row.get("オッズ"))
            if odd is None or odd <= 0:
                continue
            umaren_map[_pair_key(nums[0], nums[1])] = odd

    umatan_dir_map: dict[tuple[str, str], float] = {}
    if umatan is not None and not umatan.empty and {"組み合わせ", "オッズ"}.issubset(set(umatan.columns)):
        for _, row in umatan.iterrows():
            nums = _combo_numbers(row.get("組み合わせ"))
            if len(nums) != 2:
                continue
            if any(n in excluded for n in nums):
                continue
            odd = _parse_odds_value(row.get("オッズ"))
            if odd is None or odd <= 0:
                continue
            umatan_dir_map[(nums[0], nums[1])] = odd

    pair_rows: list[dict[str, object]] = []
    all_pairs = set(umaren_map.keys())
    for a, b in list(umatan_dir_map.keys()):
        all_pairs.add(_pair_key(a, b))

    for a, b in sorted(all_pairs, key=lambda x: (_horse_sort_key(x[0]), _horse_sort_key(x[1]))):
        ab = umatan_dir_map.get((a, b))
        ba = umatan_dir_map.get((b, a))
        synth_umatan = _synthetic_odds([x for x in [ab, ba] if x is not None])
        compare_umatan = (synth_umatan / 2.0) if synth_umatan is not None else None
        umaren_odd = umaren_map.get((a, b))
        pair_rows.append(
            {
                "馬番A": int(a) if a.isdigit() else a,
                "馬名A": horse_name_map.get(a, ""),
                "馬番B": int(b) if b.isdigit() else b,
                "馬名B": horse_name_map.get(b, ""),
                "馬連オッズ": round(umaren_odd, 4) if umaren_odd is not None else None,
                "馬単表裏合成オッズ": round(compare_umatan, 4) if compare_umatan is not None else None,
            }
        )

    pair_df = pd.DataFrame(pair_rows)
    if pair_df.empty:
        return pair_df
    return _add_spread_column(pair_df, ["馬連オッズ", "馬単表裏合成オッズ"])


def predict_from_csv_dir(csv_dir: str | Path, excluded_horses: list[str] | None = None) -> PredictionResult:
    base_dir = Path(csv_dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"CSVディレクトリが見つかりません: {base_dir}")

    excluded = {str(x).strip() for x in (excluded_horses or []) if str(x).strip()}

    frames, loaded_files = _load_csv_map(base_dir)
    tansho = frames.get("単勝")
    if tansho is None or tansho.empty:
        raise ValueError("単勝.csv が必要です。")

    master = _build_horse_master(tansho, excluded)
    horse_numbers = [str(x) for x in master["馬番"].tolist()]
    horse_name_map = {str(row["馬番"]): row["馬名"] for _, row in master.iterrows()}

    umatan_first = _collect_horse_flow_odds(frames.get("馬単"), horse_numbers, excluded, mode="position", position=0)
    umatan_second = _collect_horse_flow_odds(frames.get("馬単"), horse_numbers, excluded, mode="position", position=1)
    sanrentan_first = _collect_horse_flow_odds(frames.get("三連単"), horse_numbers, excluded, mode="position", position=0)
    sanrentan_second = _collect_horse_flow_odds(frames.get("三連単"), horse_numbers, excluded, mode="position", position=1)
    sanrentan_third = _collect_horse_flow_odds(frames.get("三連単"), horse_numbers, excluded, mode="position", position=2)
    umaren_flow = _collect_horse_flow_odds(frames.get("馬連"), horse_numbers, excluded, mode="contains")
    wide_flow = _collect_horse_flow_odds(frames.get("ワイド"), horse_numbers, excluded, mode="contains")
    sanrenpuku_flow = _collect_horse_flow_odds(frames.get("三連複"), horse_numbers, excluded, mode="contains")

    fukusho_map: dict[str, float | None] = {}
    fukusho = frames.get("複勝")
    if fukusho is not None and not fukusho.empty and {"馬番", "オッズ"}.issubset(set(fukusho.columns)):
        for _, row in fukusho.iterrows():
            horse_no = str(row.get("馬番", "")).strip()
            if horse_no and horse_no not in excluded:
                fukusho_map[horse_no] = _parse_odds_value(row.get("オッズ"))

    all_market_compare = master[["馬番", "馬名", "単勝オッズ"]].copy()
    all_market_compare["複勝オッズ"] = all_market_compare["馬番"].astype(str).map(fukusho_map)
    all_market_compare["馬連流し合成オッズ"] = all_market_compare["馬番"].astype(str).map(umaren_flow)
    all_market_compare["ワイド流し合成オッズ"] = all_market_compare["馬番"].astype(str).map(wide_flow)
    all_market_compare["馬単(1着流し)合成オッズ"] = all_market_compare["馬番"].astype(str).map(umatan_first)
    all_market_compare["馬単(2着流し)合成オッズ"] = all_market_compare["馬番"].astype(str).map(umatan_second)
    all_market_compare["三連複流し合成オッズ"] = all_market_compare["馬番"].astype(str).map(sanrenpuku_flow)
    all_market_compare["三連単(1着流し)合成オッズ"] = all_market_compare["馬番"].astype(str).map(sanrentan_first)
    all_market_compare["三連単(2着流し)合成オッズ"] = all_market_compare["馬番"].astype(str).map(sanrentan_second)
    all_market_compare["三連単(3着流し)合成オッズ"] = all_market_compare["馬番"].astype(str).map(sanrentan_third)
    all_market_compare["馬番"] = pd.to_numeric(all_market_compare["馬番"], errors="coerce").astype("Int64")
    all_market_compare = _add_spread_column(
        all_market_compare,
        [
            "単勝オッズ",
            "複勝オッズ",
            "馬連流し合成オッズ",
            "ワイド流し合成オッズ",
            "馬単(1着流し)合成オッズ",
            "馬単(2着流し)合成オッズ",
            "三連複流し合成オッズ",
            "三連単(1着流し)合成オッズ",
            "三連単(2着流し)合成オッズ",
            "三連単(3着流し)合成オッズ",
        ],
    )

    first_place_compare = master[["馬番", "馬名", "単勝オッズ"]].copy()
    first_place_compare["馬単(1着流し)合成オッズ"] = first_place_compare["馬番"].astype(str).map(umatan_first)
    first_place_compare["三連単(1着流し)合成オッズ"] = first_place_compare["馬番"].astype(str).map(sanrentan_first)
    first_place_compare["馬番"] = pd.to_numeric(first_place_compare["馬番"], errors="coerce").astype("Int64")
    first_place_compare = _add_spread_column(
        first_place_compare,
        ["単勝オッズ", "馬単(1着流し)合成オッズ", "三連単(1着流し)合成オッズ"],
    )

    flow_compare = master[["馬番", "馬名", "単勝オッズ"]].copy()
    flow_compare["馬連流し合成オッズ"] = flow_compare["馬番"].astype(str).map(umaren_flow)
    flow_compare["三連複流し合成オッズ"] = flow_compare["馬番"].astype(str).map(sanrenpuku_flow)
    flow_compare["馬番"] = pd.to_numeric(flow_compare["馬番"], errors="coerce").astype("Int64")
    flow_compare = _add_spread_column(
        flow_compare,
        ["単勝オッズ", "馬連流し合成オッズ", "三連複流し合成オッズ"],
    )

    pair_compare = _build_pair_compare(
        frames.get("馬連"),
        frames.get("馬単"),
        horse_name_map,
        excluded,
    )

    excluded_num = {int(x) for x in excluded if x.isdigit()}

    if excluded_num:
        all_market_compare = all_market_compare[~all_market_compare["馬番"].isin(excluded_num)].reset_index(drop=True)
        first_place_compare = first_place_compare[~first_place_compare["馬番"].isin(excluded_num)].reset_index(drop=True)
        flow_compare = flow_compare[~flow_compare["馬番"].isin(excluded_num)].reset_index(drop=True)
        if not pair_compare.empty:
            pair_compare = pair_compare[
                (~pair_compare["馬番A"].isin(excluded_num)) & (~pair_compare["馬番B"].isin(excluded_num))
            ].reset_index(drop=True)

    return PredictionResult(
        all_market_compare=all_market_compare,
        first_place_compare=first_place_compare,
        flow_compare=flow_compare,
        pair_compare=pair_compare,
        loaded_files=loaded_files,
        excluded_horses=sorted(excluded, key=_horse_sort_key),
    )
