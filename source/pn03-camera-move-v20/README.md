# P.N.03 カメラ相対移動 v0.20（調整メニューから RUN／HOLD を外す）

日本版 **GPNJ08** 用（`GPNJ08-camera-move-v20.patch.txt`）と北米版 **GPNE08** 用（`GPNE08-camera-move-v20.patch.txt`）。v0.19（Z ターンのカメラ要求を入りのフレームで、速さはカメラ v0.11 が彼女に合わせる。2026-10-08 ユーザー確認済み）から、調整メニューの整理だけ。**カメラ v0.11 と組で使う**。

## 変えたこと（ユーザー判断 2026-10-08）

「Mode RUN／HOLD をこれから調整することがないなら、デバッグメニューから消して、カメラのセンシ調整と Jump Window だけ残す」。

- 調整モード（L+R+Z）の **Y（RUN／HOLD 切替）を廃止**。3 行目の表示は `JUMP WIN 04 A/B` だけになり、`MODE RUN  Y` の部分が消えた。
- HOLD は移動 v0.8 までの「スティックを倒したら必ずウィンドウぶん待つ」挙動で、v0.10〜v0.11 の RUN 方式（下セクターのときだけ条件つきで待つ、実質 0 コマ応答）を入れたときに A/B 比較用に残していたもの。RUN が確認済みの挙動なので、もう切り替える理由がない。
- 設定ブロック flags bit2（HOLD）はメニューから立てられなくなった。コード内の HOLD 分岐は残っているが到達しない（新規ブロックは flags を 0 で初期化）。
- 調整モード中の Y はこれまでどおりパッド語から消す（ヴァネッサがしゃがまないように）。
- モード文字列を持っていたデータ語 4 つ（`+0x70`〜`+0x7C`）が無くなり、以後のデータ語は 0x10 ずつ前に詰まった（参照は全部名前経由なので影響なし。`turn_quarter` は `+0x8C`）。
- それ以外は v0.19 と同じ。

**ゲーム内での v0.20 の動作は未確認（表示の変化だけ）。**

## 導入

Claude 側で `GameSettings\GPNJ08.ini`・`GPNE08.ini` の `[OnFrame]` に `Camera Relative Movement v0.20` として反映済み（2026-10-08。v0.19 以前は無効で残置）。日本版は ISO 確認のために OFF にしていた他の 8 本も同時に ON へ戻した。ゲームを起動し直せば反映される。

## 調整メニュー（v0.20 時点）

| 操作 | 内容 |
|---|---|
| L+R+Z | 開く／閉じる（開いている間ヴァネッサは止まる。カメラは動く） |
| D-pad 上／下 | カメラ感度 ±1.00 倍（0.0006 刻み） |
| D-pad 左／右 | カメラ感度 ±0.0001（微調整） |
| A／B | ジャンプウィンドウ ±1 コマ（0〜30。既定 4。0 で同時入力判定なし） |
| X | 感度とウィンドウを既定値に戻す |

値は RAM 上なので再起動で既定に戻る。固定したい値はビルド時の既定値（`config_lines`）で。

## 検証

- Unicorn 2.1.4 で 7,989 ケース通過（JP／US × OnFrame／DOL 焼き込みの 4 通り。v0.19 と同じ項目で、調整モードの Y が flags を変えないこと、3 行目の文字列が `JUMP WIN nn A/B` になることを確認）。
- 配備 INI の統合テスト（`test_ini_chain.py`）JP 8／US 9 ケース。
- paired-single 退避／復帰と GQR 命令はテスト時 NOP。**Dolphin 実行は未確認。**

## ソース

`source/`（日本版）と `source-us/`（北米版）: `build_move_v20.py`、`move.s` / `move.bin`（4,204 / 4,148 bytes）、`move.dis.txt`、`patch.txt`（1,052 / 1,038 行）、`test_move_v20.py`、`sample_turn.py`、`dolphin_live_mram.py`、`dol.py`、`fn.py`、`regions.py`、`make_regions.py`、`manifest.json`、`unit-test-results.json`、`requirements.txt`。
