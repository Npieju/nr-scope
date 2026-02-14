from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


BET_TYPES = ["単勝", "複勝", "枠連", "馬連", "ワイド", "馬単", "三連複", "三連単"]

BET_WEIGHTS = {
    "単勝": 1.00,
    "複勝": 0.80,
    "枠連": 0.00,
    "馬連": 0.45,
    "ワイド": 0.35,
    "馬単": 0.55,
    "三連複": 0.30,
    "三連単": 0.40,
}


@dataclass
class PredictionResult:
    ranking: pd.DataFrame
    score_breakdown: pd.DataFrame
    loaded_files: list[str]


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
        numbers: list[float] = []
        for part in parts:
            try:
                numbers.append(float(part))
            except ValueError:
                continue
        if not numbers:
            return None
        return sum(numbers) / len(numbers)

    try:
        return float(text)
    except ValueError:
        return None


def _implied_strength(odds: float | None) -> float:
    if odds is None or odds <= 0:
        return 0.0
    return 1.0 / odds


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


def predict_from_csv_dir(csv_dir: str | Path) -> PredictionResult:
    base_dir = Path(csv_dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"CSVディレクトリが見つかりません: {base_dir}")

    frames, loaded_files = _load_csv_map(base_dir)
    tansho = frames.get("単勝")
    if tansho is None or tansho.empty:
        raise ValueError("単勝.csv が必要です。")

    required_cols = {"馬番", "馬名", "オッズ"}
    if not required_cols.issubset(set(tansho.columns)):
        raise ValueError("単勝.csv に必要な列（馬番, 馬名, オッズ）がありません。")

    horse_map: dict[str, str] = {}
    for _, row in tansho.iterrows():
        horse_no = str(row.get("馬番", "")).strip()
        horse_name = str(row.get("馬名", "")).strip()
        if horse_no:
            horse_map[horse_no] = horse_name

    scores = {horse_no: 0.0 for horse_no in horse_map}
    breakdown_rows: list[dict[str, object]] = []

    for bet_type, frame in frames.items():
        weight = BET_WEIGHTS.get(bet_type, 0.0)
        if weight <= 0:
            continue

        if bet_type in {"単勝", "複勝"}:
            if not {"馬番", "オッズ"}.issubset(set(frame.columns)):
                continue
            for _, row in frame.iterrows():
                horse_no = str(row.get("馬番", "")).strip()
                if horse_no not in scores:
                    continue
                odds = _parse_odds_value(row.get("オッズ"))
                contribution = weight * _implied_strength(odds)
                scores[horse_no] += contribution
                breakdown_rows.append(
                    {
                        "券種": bet_type,
                        "組み合わせ": horse_no,
                        "オッズ": odds,
                        "寄与先": horse_no,
                        "寄与スコア": contribution,
                    }
                )
            continue

        if not {"組み合わせ", "オッズ"}.issubset(set(frame.columns)):
            continue

        for _, row in frame.iterrows():
            combo = str(row.get("組み合わせ", "")).strip()
            if not combo:
                continue
            horse_numbers = [item.strip() for item in combo.split("-") if item.strip()]
            target_numbers = [horse_no for horse_no in horse_numbers if horse_no in scores]
            if not target_numbers:
                continue

            odds = _parse_odds_value(row.get("オッズ"))
            base_strength = _implied_strength(odds)
            if base_strength <= 0:
                continue

            contribution = (weight * base_strength) / len(target_numbers)
            for horse_no in target_numbers:
                scores[horse_no] += contribution
                breakdown_rows.append(
                    {
                        "券種": bet_type,
                        "組み合わせ": combo,
                        "オッズ": odds,
                        "寄与先": horse_no,
                        "寄与スコア": contribution,
                    }
                )

    ranking_rows: list[dict[str, object]] = []
    max_score = max(scores.values()) if scores else 0.0

    for horse_no, raw_score in scores.items():
        normalized = (raw_score / max_score * 100.0) if max_score > 0 else 0.0
        ranking_rows.append(
            {
                "馬番": horse_no,
                "馬名": horse_map.get(horse_no, ""),
                "予想スコア": round(normalized, 2),
                "生スコア": round(raw_score, 6),
            }
        )

    ranking = pd.DataFrame(ranking_rows)
    if not ranking.empty:
        ranking["馬番_int"] = pd.to_numeric(ranking["馬番"], errors="coerce")
        ranking = ranking.sort_values(by=["予想スコア", "馬番_int"], ascending=[False, True])
        ranking = ranking.drop(columns=["馬番_int"]).reset_index(drop=True)
        ranking.insert(0, "順位", range(1, len(ranking) + 1))

    breakdown = pd.DataFrame(breakdown_rows)
    return PredictionResult(ranking=ranking, score_breakdown=breakdown, loaded_files=loaded_files)
