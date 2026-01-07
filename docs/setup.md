# セットアップガイド

amatsukaze-logの詳細なセットアップ手順を説明します。

## 前提条件

### 必須要件

- Docker 20.10以降
- Docker Compose v2.0以降
- 外部Loki/Grafanaサーバー（可視化用）

### オプション要件

- Zabbixサーバー（アラート用）
- 外部Vectorサーバー（集約構成用）

## クイックスタート

### 1. リポジトリクローン

```bash
git clone https://github.com/ttrip-ngs/amatsukaze-log.git
cd amatsukaze-log
```

### 2. 設定ファイル作成

```bash
# 設定ファイルをコピー
cp config/config.example.yaml config/config.yaml
```

### 3. 環境変数設定

```bash
# 外部Lokiエンドポイントを設定（必須）
export LOKI_ENDPOINT=http://your-loki-server:3100
```

### 4. 開発環境起動

```bash
docker compose -f docker-compose.dev.yml up -d
```

### 5. 動作確認

```bash
# ログ確認
docker compose -f docker-compose.dev.yml logs -f collector

# サンプルログファイルを配置
cp /path/to/sample.json tmp/sample_log/
cp /path/to/sample.txt tmp/sample_log/
```

## 詳細設定

### 設定ファイル（config/config.yaml）

#### ログ監視設定

```yaml
watcher:
  # Amatsukazeログディレクトリ（必須）
  log_directory: /var/log/amatsukaze

  # 監視対象ファイルパターン
  file_pattern: "*.json"

  # TXTファイル待機時間（秒）
  # JSONファイル検知後、対応するTXTファイルの生成を待つ時間
  txt_wait_timeout: 30

  # ポーリング間隔（秒）
  polling_interval: 5
```

#### ログ書き込み設定

```yaml
writer:
  # Vector用ログファイル出力設定
  vector:
    enabled: true
    log_directory: /data/logs/vector
    rotate_size: 104857600  # 100MB

  # rsyslogd用ログファイル出力設定（CRITICALのみ）
  syslog:
    enabled: true
    log_directory: /data/logs/syslog
    rotate_size: 104857600  # 100MB

  # 処理済みログ管理DB設定
  database:
    path: /data/processed_logs.db
```

#### CRITICALルール設定

CRITICALルールには2種類のタイプがあります。

**パターンルール（正規表現マッチ）**

```yaml
parser:
  critical_rules:
    - name: "exception"
      type: "pattern"
      pattern: "Exception thrown"
      enabled: true

    - name: "error_termination"
      type: "pattern"
      pattern: "エラー.*終了します"
      enabled: true

    - name: "failed"
      type: "pattern"
      pattern: "failed to"
      case_sensitive: false  # 大文字小文字を区別しない
      enabled: true
```

**条件式ルール（統計値評価）**

```yaml
parser:
  critical_rules:
    # 音ずれ検出: 100ms以上
    - name: "audio_desync"
      type: "condition"
      condition: "audiodiff.maxdiff > 100.0"
      enabled: true
      message: "音ずれ検出: {audiodiff.maxdiff}ms"

    # 圧縮率異常（大ファイル限定）
    - name: "low_compression"
      type: "condition"
      condition: "compression_ratio < 3.0 and src_filesize > 10000000000"
      enabled: false
```

**条件式で使用可能なフィールド**

| フィールド | 説明 |
|-----------|------|
| `compression_ratio` | 圧縮率（入力サイズ / 出力サイズ） |
| `src_filesize` | 入力ファイルサイズ（bytes） |
| `out_filesize` | 出力ファイルサイズ（bytes） |
| `src_duration` | 入力再生時間（秒） |
| `out_duration` | 出力再生時間（秒） |
| `audiodiff.maxdiff` | 最大音ずれ（ms） |
| `audiodiff.avgdiff` | 平均音ずれ（ms） |
| `audiodiff.notincludedper` | 音声フレームロス率（%） |

**条件式でサポートする演算子**

- 比較: `>`, `<`, `>=`, `<=`, `==`, `!=`
- 論理: `and`, `or`, `not`
- 括弧: `( )`
- 算術: `+`, `-`, `*`, `/`, `%`, `**`

### 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `LOKI_ENDPOINT` | 外部LokiのURL | - |
| `VECTOR_ENDPOINT` | 外部VectorのURL（Vector経由の場合） | - |
| `LOG_LEVEL` | ログレベル（DEBUG, INFO, WARNING, ERROR） | INFO |
| `ENVIRONMENT` | 実行環境（development, production） | production |

## Vector設定

### 外部Loki直接送信（config/vector.toml）

標準設定では外部Lokiサーバーに直接送信します。

```toml
[sinks.loki_external]
type = "loki"
inputs = ["add_labels"]
endpoint = "${LOKI_ENDPOINT:-http://loki:3100}"
encoding.codec = "json"

[sinks.loki_external.labels]
service = "{{ service }}"
environment = "{{ environment }}"
host = "{{ host }}"
status = "{{ status }}"
severity = "{{ severity }}"
encoder = "{{ encoder }}"
```

### 外部Vector経由送信

集約構成で外部Vectorに送信する場合は、`config/vector.toml`の`loki_external`セクションをコメントアウトし、`vector_external`セクションを有効化してください。

```toml
[sinks.vector_external]
type = "vector"
inputs = ["add_labels"]
address = "${VECTOR_ENDPOINT:-vector-server:9000}"
version = "2"
```

## rsyslogd設定

CRITICALエラーをZabbixに通知するためのrsyslogd設定です。

### config/rsyslog.conf

```conf
# rsyslogdがcollectorが書き込んだsyslogファイルを読み取り
module(load="imfile")
input(type="imfile"
      File="/data/logs/syslog/amatsukaze.log"
      Tag="amatsukaze"
      Severity="error"
      Facility="local0")

# Zabbixサーバーへ転送
*.* action(type="omfwd"
           target="zabbix-server"
           port="10514"
           protocol="udp")
```

## Docker構成

### 開発環境（docker-compose.dev.yml）

```bash
# 起動
docker compose -f docker-compose.dev.yml up -d

# ログ確認
docker compose -f docker-compose.dev.yml logs -f collector

# コンテナに入る
docker compose -f docker-compose.dev.yml exec collector bash

# 停止
docker compose -f docker-compose.dev.yml down
```

### 本番環境（docker-compose.yml）

```bash
# 設定ファイル準備
cp config/config.example.yaml config/config.yaml
# config/config.yaml を環境に合わせて編集

# 環境変数設定
export LOKI_ENDPOINT=http://your-loki-server:3100

# 起動
docker compose up -d

# 停止
docker compose down
```

### ボリューム構成

| ボリューム | コンテナパス | 用途 |
|-----------|-------------|------|
| ホストログディレクトリ | `/var/log/amatsukaze` | Amatsukazeログ（読み取り専用） |
| collector-data | `/data` | 処理済みDB、一時ファイル |
| vector-data | `/var/lib/vector` | Vectorステート |
| syslog-data | `/data/logs/syslog` | syslogファイル |

## テスト実行

### 全テスト実行

```bash
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/ -v
```

### カバレッジ付き

```bash
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/ --cov=src
```

### 特定テスト

```bash
# パーサーテストのみ
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/unit/test_parser.py -v

# 条件式評価テストのみ
docker compose -f docker-compose.dev.yml exec collector python -m pytest tests/unit/test_condition_evaluator.py -v
```

## コード品質チェック

### Lint

```bash
docker compose -f docker-compose.dev.yml exec collector python -m ruff check .
```

### Format

```bash
docker compose -f docker-compose.dev.yml exec collector python -m ruff format .
```

### 型チェック

```bash
docker compose -f docker-compose.dev.yml exec collector python -m mypy src
```

## トラブルシューティング

### ログファイルが検出されない

1. ログディレクトリがマウントされているか確認

```bash
docker compose -f docker-compose.dev.yml exec collector ls -la /var/log/amatsukaze
```

2. ファイルパターンが正しいか確認

```yaml
watcher:
  file_pattern: "*.json"  # デフォルト
```

3. watcherログを確認

```bash
docker compose -f docker-compose.dev.yml logs collector | grep -i watcher
```

### Vector送信エラー

1. 外部Lokiに接続できるか確認

```bash
curl -X GET ${LOKI_ENDPOINT}/ready
```

2. Vector設定を確認

```bash
docker compose -f docker-compose.dev.yml exec vector vector validate /etc/vector/vector.toml
```

3. Vectorログを確認

```bash
docker compose -f docker-compose.dev.yml logs vector
```

### CRITICALが検出されない

1. ルールが有効化されているか確認

```yaml
critical_rules:
  - name: "exception"
    type: "pattern"
    enabled: true  # falseになっていないか確認
```

2. パターンがマッチするか確認

```bash
# テストで確認
docker compose -f docker-compose.dev.yml exec collector python -c "
import re
pattern = 'Exception thrown'
log_line = 'AMT [error] Exception thrown at TranscodeManager.cpp:593'
print('Match:', bool(re.search(pattern, log_line)))
"
```

### SQLiteエラー

1. DBファイルのパーミッションを確認

```bash
docker compose -f docker-compose.dev.yml exec collector ls -la /data/
```

2. DBファイルを再作成

```bash
docker compose -f docker-compose.dev.yml exec collector rm /data/processed_logs.db
docker compose -f docker-compose.dev.yml restart collector
```

## 参照ドキュメント

- [アーキテクチャ設計書](architecture.md)
- [README](../README.md)
- [タスク管理](../TASKS.md)
