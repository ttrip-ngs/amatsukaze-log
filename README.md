# amatsukaze-log

Amatsukazeエンコーダのログを収集し、Loki/Grafanaで可視化、Zabbixでアラート管理を行うシステム。

## 概要

現在、Windowsクライアントでしか確認できないAmatsukazeのエンコード状況をWebベース（Grafana）で監視可能にします。

### 主な機能

- エンコードログの自動収集（inotify監視）
- 構造化データへの変換（TXT + JSON解析）
- Loki/Grafanaでの可視化
- CRITICALエラーのZabbixアラート

## アーキテクチャ

```
Amatsukazeログ(txt/json)
    ↓
[ログ収集コンテナ (Python)]
    ↓
    ├─→ Vector → Loki → Grafana
    └─→ rsyslogd → Vector → Zabbix
```

詳細は [docs/architecture.md](docs/architecture.md) を参照してください。

## クイックスタート

### 開発環境

```bash
# リポジトリクローン
git clone https://github.com/ttrip-ngs/amatsukaze-log.git
cd amatsukaze-log

# 開発環境起動（Docker Compose）
docker compose -f docker-compose.dev.yml up

# Grafana にアクセス
open http://localhost:3000
```

### 本番環境

```bash
# 設定ファイル作成
cp config/config.example.yaml config/config.yaml
# config/config.yaml を編集

# コンテナ起動
docker compose up -d
```

## 開発

### 必要要件

- Docker & Docker Compose
- Python 3.11+ (ローカル開発時)

### 開発環境セットアップ

```bash
# 開発用コンテナ起動
docker compose -f docker-compose.dev.yml up -d

# ログ確認
docker compose -f docker-compose.dev.yml logs -f collector

# テスト実行
docker compose -f docker-compose.dev.yml exec collector pytest

# Lint/Format
docker compose -f docker-compose.dev.yml exec collector ruff check .
docker compose -f docker-compose.dev.yml exec collector ruff format .

# 型チェック
docker compose -f docker-compose.dev.yml exec collector mypy src
```

### プロジェクト構造

```
amatsukaze-log/
├── src/
│   ├── collector/       # ログ収集・解析
│   ├── models/          # データモデル
│   └── utils/           # ユーティリティ
├── tests/               # テスト
├── config/              # 設定ファイル
├── docker/              # Docker関連
├── docs/                # ドキュメント
└── grafana/             # Grafanaダッシュボード
```

## 設定

### config/config.yaml

```yaml
watcher:
  log_directory: /var/log/amatsukaze
  file_pattern: "*.json"

sender:
  vector:
    enabled: true
    endpoint: "http://vector:9000/amatsukaze"
  syslog:
    enabled: true
    host: "rsyslogd"
    port: 514
```

詳細は [config/config.example.yaml](config/config.example.yaml) を参照してください。

## ドキュメント

- [アーキテクチャ設計書](docs/architecture.md)
- [セットアップガイド](docs/setup.md)（作成予定）
- [API仕様](docs/api.md)（作成予定）

## タスク管理

実装状況は [TASKS.md](TASKS.md) を参照してください。

## ライセンス

MIT License

## 貢献

Issue、Pull Requestを歓迎します。

## 関連リンク

- [Amatsukaze](https://github.com/nekopanda/Amatsukaze)
- [Vector](https://vector.dev/)
- [Grafana Loki](https://grafana.com/oss/loki/)
