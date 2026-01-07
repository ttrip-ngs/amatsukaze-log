# amatsukaze-log

Amatsukazeエンコーダのログを収集し、Loki/Grafanaで可視化、Zabbixでアラート管理を行うシステム。

## 概要

現在、Windowsクライアントでしか確認できないAmatsukazeのエンコード状況をWebベース（Grafana）で監視可能にします。

### 主な機能

- エンコードログの自動収集（watchdog/inotify監視）
- 構造化データへの変換（TXT + JSON解析）
- YAMLベースのカスタムCRITICALルール
- Loki/Grafanaでの可視化
- CRITICALエラーのZabbixアラート（rsyslogd経由）

## アーキテクチャ

```
Amatsukazeログ(txt/json)
    ↓
[ログ収集コンテナ (Python)]  ← Docker (collector)
    ↓ ファイル出力
    ├─→ JSONLファイル (/data/logs/vector/)
    │     ↓
    │   [Vector (ローカル)]  ← Docker (vector)
    │     ↓ 外部送信
    │   Loki (外部サーバー) → Grafana
    │
    └─→ syslogファイル (/data/logs/syslog/)  ← CRITICALのみ
          ↓
        [rsyslogd (ローカル)]  ← Docker (rsyslogd)
          ↓
        Zabbix (アラート)
```

詳細は [docs/architecture.md](docs/architecture.md) を参照してください。

## クイックスタート

### 前提条件

- Docker & Docker Compose
- 外部Loki/Grafanaサーバー（可視化用）
- Zabbixサーバー（アラート用、オプション）

### 開発環境

```bash
# リポジトリクローン
git clone https://github.com/ttrip-ngs/amatsukaze-log.git
cd amatsukaze-log

# 環境変数設定（外部Lokiエンドポイント）
export LOKI_ENDPOINT=http://your-loki-server:3100

# 開発環境起動
docker compose -f docker-compose.dev.yml up -d

# ログ確認
docker compose -f docker-compose.dev.yml logs -f collector

# サンプルログでテスト（tmp/sample_logにログファイルを配置）
```

### 本番環境

```bash
# 設定ファイル作成
cp config/config.example.yaml config/config.yaml
# config/config.yaml を編集

# 環境変数設定
export LOKI_ENDPOINT=http://your-loki-server:3100

# コンテナ起動
docker compose up -d
```

## 設定

### config/config.yaml

```yaml
# ログファイル監視設定
watcher:
  log_directory: /var/log/amatsukaze  # Amatsukazeログディレクトリ
  file_pattern: "*.json"
  txt_wait_timeout: 30  # TXTファイル待機時間（秒）

# ログ書き込み設定
writer:
  vector:
    enabled: true
    log_directory: /data/logs/vector  # Vector用ログ出力先
    rotate_size: 104857600  # 100MB
  syslog:
    enabled: true
    log_directory: /data/logs/syslog  # syslog用ログ出力先（CRITICALのみ）

# パーサー設定
parser:
  encoding: utf-8-sig
  critical_rules:
    - name: "exception"
      type: "pattern"
      pattern: "Exception thrown"
      enabled: true
    - name: "audio_desync"
      type: "condition"
      condition: "audiodiff.maxdiff > 100.0"
      enabled: true
```

詳細は [config/config.example.yaml](config/config.example.yaml) を参照してください。

### 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `LOKI_ENDPOINT` | 外部LokiのURL | - |
| `VECTOR_ENDPOINT` | 外部VectorのURL（Vector経由の場合） | - |
| `LOG_LEVEL` | ログレベル | INFO |
| `ENVIRONMENT` | 実行環境 | production |

## 開発

### テスト実行

```bash
# 全テスト実行
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/ -v

# カバレッジ付き
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/ --cov=src

# 特定テスト
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/unit/test_parser.py -v
```

### コード品質チェック

```bash
# Lint
docker compose -f docker-compose.dev.yml exec collector python -m ruff check .

# Format
docker compose -f docker-compose.dev.yml exec collector python -m ruff format .

# 型チェック
docker compose -f docker-compose.dev.yml exec collector python -m mypy src
```

### プロジェクト構造

```
amatsukaze-log/
├── src/
│   ├── collector/           # ログ収集・解析
│   │   ├── parser.py        # ログパーサー
│   │   ├── watcher.py       # ファイル監視
│   │   ├── writer.py        # ログファイル出力
│   │   └── database.py      # 処理済み管理DB
│   ├── models/              # データモデル
│   │   ├── config.py        # 設定モデル
│   │   └── log_entry.py     # ログエントリモデル
│   ├── utils/               # ユーティリティ
│   │   └── condition_evaluator.py  # 条件式評価
│   └── main.py              # エントリーポイント
├── tests/                   # テスト（55件、75%カバレッジ）
├── config/                  # 設定ファイル
│   ├── config.yaml          # アプリケーション設定
│   ├── vector.toml          # Vector設定
│   └── rsyslog.conf         # rsyslog設定
├── docs/                    # ドキュメント
└── docker-compose.yml       # 本番用
└── docker-compose.dev.yml   # 開発用
```

## CRITICALルール

YAMLでカスタムCRITICALルールを定義できます。

### パターンルール（正規表現）

```yaml
critical_rules:
  - name: "exception"
    type: "pattern"
    pattern: "Exception thrown"
    enabled: true
```

### 条件式ルール

```yaml
critical_rules:
  - name: "audio_desync"
    type: "condition"
    condition: "audiodiff.maxdiff > 100.0"
    enabled: true
    message: "音ずれ検出: {audiodiff.maxdiff}ms"
```

サポートする変数:
- `audiodiff.maxdiff`: 最大音ずれ（ms）
- `compression_ratio`: 圧縮率
- `src_filesize`, `out_filesize`: ファイルサイズ
- その他JSONログの全フィールド

## ドキュメント

- [アーキテクチャ設計書](docs/architecture.md)
- [セットアップガイド](docs/setup.md)
- [タスク管理](TASKS.md)

## テスト状況

- テスト数: 55件
- カバレッジ: 75%
- 主要モジュール:
  - database.py: 100%
  - condition_evaluator.py: 100%
  - parser.py: 91%
  - watcher.py: 85%
  - writer.py: 85%

## ライセンス

MIT License

## 関連リンク

- [Amatsukaze](https://github.com/nekopanda/Amatsukaze)
- [Vector](https://vector.dev/)
- [Grafana Loki](https://grafana.com/oss/loki/)
