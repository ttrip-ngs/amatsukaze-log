# CLAUDE.md

このファイルは、amatsukaze-logプロジェクトのコンテキストとガイドラインを提供します。

## プロジェクト概要

Amatsukazeエンコーダのログを収集し、Loki/Grafanaで可視化、Zabbixでアラート管理を行うシステム。
現在、Windowsクライアントでしか確認できないエンコード状況をWebベースで監視可能にする。

## システム構成

### 現状の課題
- Amatsukazeのエンコード結果はWindowsクライアントでしか確認できない
- エンコード状況の監視が困難
- エラー発生時の通知がない

### 目標
- Webブラウザ（Grafana）でエンコード状況を可視化
- CRITICALなエラーをZabbixでアラート
- 番組名、処理時間、エラー内容等で検索・フィルタリング可能

### アーキテクチャ

```
Amatsukazeログ(txt/json)
    ↓
[ログ収集コンテナ (Python)] ← Docker
    ↓
    ├─→ Vector (HTTP/TCP, JSON + Labels) ← 全ログ詳細データ
    │     ↓
    │   Vector (transform/routing)
    │     ↓
    │   Loki (保存)
    │     ↓
    │   Grafana (可視化)
    │
    └─→ rsyslogd (syslog) ← CRITICALアラートのみ
          ↓
        Vector
          ↓
        Zabbix (アラート)
```

## 技術スタック

- 言語: Python 3.11+
- コンテナ: Docker
- ログ転送: rsyslogd → Vector → Loki/Zabbix
- 可視化: Grafana
- 監視: Zabbix

## ログファイル構造

### ファイル形式
- 1エンコードタスクにつき2ファイル生成
  - `YYYY-MM-DD_HHMMSS.mmm.txt`: 詳細ログ（UTF-8 with BOM）
  - `YYYY-MM-DD_HHMMSS.mmm.json`: エンコード結果サマリ

### TXTログ構造
```
行1: コマンドライン引数
行2-: ログメッセージ
  - AMT [info] メッセージ: 情報ログ
  - AMT [warn] メッセージ: 警告
  - AMT [error] メッセージ: エラー
  - AMT [debug] メッセージ: デバッグ
  - FFMPEG [warn/error] メッセージ: FFMPEGログ
```

### JSONログ構造
```json
{
  "srcpath": "入力ファイルパス",
  "outfiles": [{
    "path": "出力ファイルパス",
    "srcbitrate": 13510,
    "outfilesize": 561277301,
    "subs": []
  }],
  "srcfilesize": 6522388528,
  "srcduration": 3614.945,
  "outduration": 3013.544,
  "error": {
    "unknown-pts": 0,
    "decode-packet-failed": 0,
    "h264-pts-mismatch": 0,
    ...
  },
  "cmanalyze": true
}
```

### エラー判定
- CRITICAL: `AMT [error] Exception thrown` が存在
- 成功: `AMT [info] Mux完了` または `AMT [info] [出力ファイル]` が存在
- 警告多発: DRCS外字警告（`AMT [warn] [字幕] マッピングのないDRCS外字`）は頻出するが非CRITICAL

## 送信データ形式

### Vector/Loki用（JSON + Labels）
```json
{
  "timestamp": "2025-10-18T01:54:20.932Z",
  "message": "エンコード完了: [新]緊急取調室 #1",

  "labels": {
    "service": "amatsukaze",
    "environment": "production",
    "host": "encoder-01",
    "status": "success",
    "severity": "info",
    "encoder": "QSVEnc"
  },

  "task_id": "2025-10-18_015420.932",
  "program_name": "[新]緊急取調室 #1[解][字]",
  "src_path": "/REC_01/TV-Record/...",
  "src_duration": 3614.945,
  "out_duration": 3013.544,
  "src_filesize": 6522388528,
  "out_filesize": 561277301,
  "compression_ratio": 8.6,
  "error_message": "エラー内容",
  "error_count": {"warn": 87, "error": 1},
  "format": "Matroska"
}
```

Grafanaでのクエリ例:
```
{service="amatsukaze", status="failed"}
{service="amatsukaze", severity="critical"}
{service="amatsukaze", encoder="QSVEnc"} |= "エンコード失敗"
```

### Zabbix用（syslog）
```
<Priority>timestamp hostname amatsukaze: CRITICAL: [番組名] - エンコード失敗: エラーメッセージ
```

## 実装方針

### ログ送信方式（ハイブリッド）
- 全ログ: VectorにJSON直接送信（構造化データ保持）
- CRITICALアラート: rsyslogdにsyslog送信（既存監視と統合）

### 処理タイミング
- ログファイル監視（inotify使用）
- JSONファイル作成検知で処理開始
- 対応するTXTファイルとペアで解析
- 数分程度の遅延は許容

### エラーハンドリング
- rsyslogd/Vector接続失敗: リトライ後、ログ記録
- パース失敗: エラーログ記録し、スキップ
- 重複送信防止: 送信済み管理機構を実装

## 運用要件

### ログファイル
- 保持: 元のtxt/jsonファイルは送信後も保持（Amatsukazeに削除オプションあり）
- ディレクトリ: 任意パス指定可能（設定ファイルで指定）

### コンテナ実行
- Dockerコンテナとして実行
- ログディレクトリはホストマウント
- 設定ファイルで柔軟に設定変更可能

### 遅延要件
- リアルタイム性は不要
- 数分程度の遅延は許容

## Grafanaダッシュボード要件（将来）

### 表示項目
1. エンコードタスク一覧
   - 日時、番組名、ステータス、処理時間、圧縮率
2. エラー詳細
   - エラー種別別集計、失敗タスクの詳細
3. 統計
   - 成功率グラフ、処理時間トレンド、ファイルサイズ削減率
4. リアルタイム状況
   - 最新タスク状況

## 開発ガイドライン

- Python 3.11+ 使用
- 型ヒント必須
- pytest でテスト作成
- ruff でlint/format
- Docker Compose でローカル開発環境構築
- 設定は YAML ファイルで管理
- すべての開発はDockerコンテナ内で実行
  - ローカルホストへの直接インストール不要
  - docker-compose.dev.yml で開発環境一式構築
  - ログサーバ（rsyslogd/Vector/Loki）も含めた統合開発環境

## 次のステップ

1. 詳細設計ドキュメント作成
2. タスク整理（TASKS.md）
3. プロジェクト構造作成
4. ログパーサー実装
5. ログ収集・送信機能実装
6. Docker環境構築
7. テスト実装
8. Grafanaダッシュボード雛形作成
