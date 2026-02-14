# nr-scope

`nk-tracer` が出力した券種別CSV（単勝、複勝、馬連、ワイド、馬単、三連複、三連単）を入力に、
馬ごとの予想スコアを算出して可視化する MVP アプリです。

## セットアップ

```bash
cd /home/nr-scope
pip install -r requirements.txt
```

## 起動

```bash
streamlit run app.py
```

ブラウザで開いたら、CSV ディレクトリに次のようなパスを指定して実行してください。

- `/home/nk-tracer/out/saudi_cup_csv`
- `/home/nk-tracer/out/batch/<race_id>/csv`

## 予想ロジック（MVP）

- 各券種オッズを「暗黙強度」`1 / odds` に変換
- 券種ごとの重みを掛け算
- 組み合わせ券種は、該当馬へ等分配で寄与
- 全馬のスコアを 0-100 に正規化してランキング化

### 券種重み

- 単勝: 1.00
- 複勝: 0.80
- 馬連: 0.45
- ワイド: 0.35
- 馬単: 0.55
- 三連複: 0.30
- 三連単: 0.40
- 枠連: 0.00（MVPでは馬番と直接対応しないため未使用）

## ファイル構成

- `app.py`: Streamlit UI
- `predictor.py`: CSV読込とスコア算出ロジック
- `requirements.txt`: 依存パッケージ

## 今後の拡張例

- レース結果を教師データにした学習モデル化
- 天候、馬場、距離、枠順など特徴量追加
- 複数レースのバックテスト
