# システムアーキテクチャ設計書

## 概要

Amatsukazeエンコーダのログを収集し、Loki/Grafanaで可視化、Zabbixでアラート管理を行うシステムの詳細設計。

## システム構成図

```
┌─────────────────────────────────────────────────────────────┐
│ Amatsukaze (Docker)                                         │
│  - エンコード処理                                             │
│  - ログ出力: /logs/YYYY-MM-DD_HHMMSS.mmm.{txt,json}         │
└────────────────┬────────────────────────────────────────────┘
                 │ (ホストマウント)
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ amatsukaze-log-collector (Docker)                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Log Watcher (inotify)                               │   │
│  │  - JSONファイル作成検知                              │   │
│  │  - 対応するTXTファイル読み込み                        │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 ↓                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Log Parser                                          │   │
│  │  - TXTログ解析 (ログレベル、エラーメッセージ抽出)     │   │
│  │  - JSON解析 (メタデータ、統計情報抽出)               │   │
│  │  - 構造化データ生成                                  │   │
│  └──────────────┬──────────────────────────────────────┘   │
│                 ↓                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Log Sender                                          │   │
│  │  - Vector送信 (全ログ、JSON形式)                     │   │
│  │  - rsyslogd送信 (CRITICALのみ、syslog形式)          │   │
│  │  - 送信済み管理                                      │   │
│  │  - リトライ処理                                      │   │
│  └──────────────┬──────────────────────────────────────┘   │
└─────────────────┼────────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ↓                   ↓
┌──────────────┐   ┌──────────────┐
│ Vector       │   │ rsyslogd     │
│ (HTTP/TCP)   │   │ (syslog UDP) │
│ port: 9000   │   │ port: 514    │
└──────┬───────┘   └──────┬───────┘
       │                  │
       │ transform/       │
       │ routing          ↓
       │           ┌──────────────┐
       │           │ Vector       │
       │           │ (from syslog)│
       │           └──────┬───────┘
       │                  │
       ↓                  ↓
┌──────────────┐   ┌──────────────┐
│ Loki         │   │ Zabbix       │
│ port: 3100   │   │ port: 10051  │
└──────┬───────┘   └──────────────┘
       │
       ↓
┌──────────────┐
│ Grafana      │
│ port: 3000   │
└──────────────┘
```

## コンポーネント詳細

### 1. Log Watcher

**責務:**
- Amatsukazeログディレクトリの監視
- 新規ログファイル検出
- ファイルペア（txt/json）の関連付け

**技術選定:**
- Python watchdog ライブラリ（inotify wrapper）
- 非同期I/O（asyncio）

**動作フロー:**
```
1. inotifyでディレクトリ監視
2. *.json ファイル作成イベント検知
3. 対応する *.txt ファイルの存在確認（リトライあり）
4. ファイルペアをキューに追加
5. Parserへ処理依頼
```

**設定項目:**
```yaml
watcher:
  log_directory: /var/log/amatsukaze
  file_pattern: "*.json"
  txt_wait_timeout: 30  # TXTファイル待機時間（秒）
  polling_interval: 5    # ポーリング間隔（秒）
```

### 2. Log Parser

**責務:**
- TXTログファイル解析
- JSONファイル解析
- 構造化データ生成

**解析内容:**

#### TXTログ解析
```python
{
    "command_line": "1行目のコマンドライン",
    "logs": [
        {
            "level": "info|warn|error|debug",
            "source": "AMT|FFMPEG",
            "message": "ログメッセージ",
            "timestamp_relative": "60分11.30秒"  # ログ内相対時刻
        }
    ],
    "has_critical_error": True/False,
    "error_summary": {
        "info_count": 150,
        "warn_count": 87,
        "error_count": 1,
        "critical_errors": ["Exception thrown at TranscodeManager.cpp:593"]
    },
    "phases": {
        "ts_analysis": {"status": "completed", "duration": 81.71},
        "logo_analysis": {"status": "completed", "duration": null},
        "encode": {"status": "failed", "duration": null},
        "mux": {"status": "not_started", "duration": null}
    }
}
```

#### JSON解析
```python
{
    "task_id": "2025-10-18_015420.932",
    "program_name": "番組名（srcpathから抽出）",
    "src_path": "/REC_01/TV-Record/...",
    "out_path": "/app/output/...",
    "src_filesize": 6522388528,
    "out_filesize": 561277301,
    "compression_ratio": 11.6,
    "src_duration": 3614.945,
    "out_duration": 3013.544,
    "duration_diff": 601.401,  # CM削除時間
    "error_counts": {...},
    "encoder": "QSVEnc",
    "format": "Matroska",
    "service_id": 56336
}
```

#### 統合データ（Vector送信用）
```python
{
    "timestamp": "2025-10-18T01:54:20.932Z",
    "message": "エンコード完了: [新]緊急取調室 #1",

    # Lokiラベル（Vectorでインデックス化）
    "labels": {
        "service": "amatsukaze",
        "environment": "production",
        "host": "encoder-01",
        "status": "success|failed|warning",
        "severity": "info|warning|critical",
        "encoder": "QSVEnc"
    },

    "task_id": "2025-10-18_015420.932",

    # JSONから
    "program_name": "...",
    "src_path": "...",
    "out_path": "...",
    "src_filesize": 6522388528,
    "out_filesize": 561277301,
    "compression_ratio": 11.6,
    "src_duration": 3614.945,
    "out_duration": 3013.544,
    "format": "Matroska",

    # TXTから
    "error_message": "主要エラーメッセージ",
    "error_counts": {"info": 150, "warn": 87, "error": 1},
    "phases": {...},
    "command_line": "..."
}
```

### 3. Log Sender

**責務:**
- 構造化データをVector/rsyslogdへ送信
- 送信済み管理
- エラーハンドリング・リトライ

**送信先1: Vector (全ログ)**

プロトコル: HTTP POST (JSON)
```
POST http://vector:9000/amatsukaze
Content-Type: application/json

{
  "timestamp": "2025-10-18T01:54:20.932Z",
  "task_id": "2025-10-18_015420.932",
  ...
}
```

**送信先2: rsyslogd (CRITICALのみ)**

プロトコル: syslog (UDP/TCP)
```
<11>Oct 18 01:54:20 amatsukaze-collector amatsukaze[1234]: CRITICAL: [新]緊急取調室 #1[解][字] - エンコード失敗: マッピングにないDRCS外字あり正常に字幕処理できなかったため終了します
```

facility: user (1), severity: error (3) → priority: 11

**CRITICAL判定条件（syslog/Zabbixアラート対象）:**

以下のいずれかのパターンがTXTログに含まれる場合、`severity = "critical"` となりsyslog送信される:

1. **Exceptionパターン**
   - 正規表現: `Exception thrown`
   - 例: `AMT [error] Exception thrown at TranscodeManager.cpp:593`

2. **終了エラーパターン**
   - 正規表現: `エラー.*終了します`
   - 例: `Message: マッピングにないDRCS外字あり正常に字幕処理できなかったため終了します`

3. **失敗パターン**
   - 正規表現: `failed to` (大文字小文字区別なし)
   - 例: `AMT [error] Failed to encode video stream`

**syslog送信されないケース:**

- `AMT [warn]` のみの警告（例: DRCS外字警告）
- 警告多発（50件以上）でも正常完了した場合（status = "warning", severity = "warning"）
- エンコード正常完了（status = "success", severity = "info"）

**送信済み管理:**

方式: SQLite ローカルDB
```sql
CREATE TABLE processed_logs (
    task_id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    vector_sent BOOLEAN DEFAULT 0,
    syslog_sent BOOLEAN DEFAULT 0,
    retry_count INTEGER DEFAULT 0
);
```

**リトライロジック:**
```
1. 送信失敗時、retry_count インクリメント
2. exponential backoff (1秒 → 2秒 → 4秒 → ...)
3. 最大リトライ: 5回
4. 5回失敗後、エラーログ記録してスキップ
```

**設定項目:**
```yaml
sender:
  vector:
    enabled: true
    endpoint: "http://vector:9000/amatsukaze"
    timeout: 10
    retry_max: 5

  syslog:
    enabled: true
    host: "rsyslogd"
    port: 514
    protocol: "udp"  # udp or tcp
    facility: "user"

  database:
    path: "/data/processed_logs.db"
```

## データフロー

### 正常系

```
1. Amatsukazeがエンコード完了
2. ログファイル生成: 2025-10-18_015420.932.{txt,json}
3. Watcher が json ファイル作成検知
4. Watcher が txt ファイル存在確認
5. Parser が両ファイル読み込み・解析
6. Sender が構造化データ送信
   - Vector へ JSON 送信
   - (CRITICALの場合) rsyslogd へ syslog 送信
7. DB に送信済み記録
```

### 異常系

#### ケース1: TXTファイル未生成
```
1. json ファイル検知
2. txt ファイル待機（30秒）
3. タイムアウト
4. エラーログ記録、スキップ
```

#### ケース2: パース失敗
```
1. ファイル読み込み
2. パースエラー発生
3. エラーログ記録、スキップ
4. 元ファイルは保持（手動調査用）
```

#### ケース3: Vector送信失敗
```
1. 送信エラー
2. retry_count インクリメント
3. exponential backoff 後リトライ
4. 5回失敗で諦め、エラーログ記録
```

#### ケース4: 重複処理
```
1. json ファイル検知
2. DB で task_id 検索
3. 既存レコード発見
4. スキップ（再送信しない）
```

## 設定ファイル設計

### config.yaml

```yaml
# ログ監視設定
watcher:
  log_directory: /var/log/amatsukaze
  file_pattern: "*.json"
  txt_wait_timeout: 30
  polling_interval: 5

# パーサー設定
parser:
  encoding: utf-8-sig  # UTF-8 with BOM
  max_log_lines: 10000  # 大量ログ対策

# 送信設定
sender:
  vector:
    enabled: true
    endpoint: "http://vector:9000/amatsukaze"
    timeout: 10
    retry_max: 5
    retry_backoff_base: 2  # exponential backoff base

  syslog:
    enabled: true
    host: "rsyslogd"
    port: 514
    protocol: "udp"
    facility: "user"
    severity_map:
      critical: "err"
      warning: "warning"
      info: "info"

  database:
    path: "/data/processed_logs.db"

# ログ設定
logging:
  level: INFO
  format: "json"
  output: stdout

# アプリケーション設定
app:
  worker_threads: 2  # 並列処理数
  queue_size: 100    # 処理キューサイズ
```

## ディレクトリ構造

```
amatsukaze-log/
├── src/
│   ├── collector/
│   │   ├── __init__.py
│   │   ├── watcher.py         # ログファイル監視
│   │   ├── parser.py          # ログ解析
│   │   ├── sender.py          # ログ送信
│   │   └── database.py        # 送信済み管理DB
│   ├── models/
│   │   ├── __init__.py
│   │   ├── log_entry.py       # ログエントリモデル
│   │   └── config.py          # 設定モデル
│   └── utils/
│       ├── __init__.py
│       └── logger.py          # ロギングユーティリティ
├── config/
│   ├── config.yaml            # メイン設定
│   ├── config.example.yaml    # 設定例
│   └── vector.toml            # Vector設定（参考）
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_sender.py
│   └── fixtures/              # テストデータ
│       ├── sample.txt
│       └── sample.json
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
├── scripts/
│   └── entrypoint.sh
├── grafana/
│   └── dashboards/
│       └── amatsukaze.json    # ダッシュボード定義
├── docs/
│   ├── architecture.md        # 本ファイル
│   ├── setup.md               # セットアップガイド
│   └── api.md                 # API仕様
├── requirements.txt
├── pyproject.toml
├── README.md
├── CLAUDE.md
└── TASKS.md
```

## セキュリティ考慮事項

1. **認証情報管理**
   - Vector/rsyslogd接続情報は環境変数または secrets で管理
   - config.yaml に平文パスワード記載禁止

2. **ログ情報の取り扱い**
   - 番組名等の個人情報は含まれる可能性あり
   - 必要に応じてマスキング処理実装

3. **ネットワークセキュリティ**
   - Vector/rsyslogd との通信は内部ネットワークのみ
   - 外部公開不要

4. **ファイルパーミッション**
   - ログファイル: 読み取り専用
   - DB ファイル: コンテナ内のみ書き込み可能

## パフォーマンス考慮事項

1. **ファイル監視**
   - inotify 使用（ポーリングより効率的）
   - イベントドリブンで CPU 負荷最小化

2. **並列処理**
   - asyncio で非同期 I/O
   - worker_threads で並列処理数制御

3. **メモリ管理**
   - 大量ログファイル対策: ストリーミング読み込み
   - max_log_lines でメモリ使用量制限

4. **ディスク I/O**
   - SQLite WAL モード有効化（並行読み書き）
   - バッチコミット（トランザクション最適化）

## 監視・運用

### ヘルスチェック

```bash
# コンテナヘルスチェック
curl http://localhost:8080/health

# レスポンス例
{
  "status": "healthy",
  "watcher": "running",
  "queue_size": 3,
  "processed_today": 125,
  "failed_today": 2
}
```

### メトリクス

- 処理済みタスク数
- 失敗タスク数
- キューサイズ
- 平均処理時間
- Vector/rsyslogd 送信成功率

### ログ出力

JSON Lines 形式で stdout 出力
```json
{"timestamp": "2025-10-18T01:54:20Z", "level": "INFO", "message": "Processing task 2025-10-18_015420.932"}
{"timestamp": "2025-10-18T01:54:21Z", "level": "ERROR", "message": "Failed to send to Vector", "task_id": "..."}
```

## 開発環境

### Docker Compose構成

すべての開発はDockerコンテナ内で実行する。

#### docker-compose.dev.yml

```yaml
services:
  # 開発対象：ログ収集コンテナ
  amatsukaze-log-collector:
    build: .
    volumes:
      - ./src:/app/src:ro
      - ./config:/app/config:ro
      - ./tmp/sample_log:/var/log/amatsukaze:ro
      - collector-data:/data
    environment:
      - LOG_LEVEL=DEBUG
      - ENVIRONMENT=development
    depends_on:
      - vector
      - rsyslogd

  # ログサーバ群
  rsyslogd:
    image: rsyslog/syslog_appliance_alpine:latest
    ports:
      - "514:514/udp"
    volumes:
      - ./config/rsyslog.conf:/etc/rsyslog.conf:ro

  vector:
    image: timberio/vector:latest-alpine
    ports:
      - "9000:9000"
    volumes:
      - ./config/vector.toml:/etc/vector/vector.toml:ro
    depends_on:
      - loki

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
    volumes:
      - ./config/loki.yaml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - grafana-data:/var/lib/grafana
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    depends_on:
      - loki

volumes:
  collector-data:
  loki-data:
  grafana-data:
```

### 開発フロー

1. `docker compose -f docker-compose.dev.yml up` で環境起動
2. コード編集（ホットリロード対応）
3. Grafana（http://localhost:3000）で動作確認
4. `docker compose -f docker-compose.dev.yml logs -f collector` でログ確認

### テスト実行

```bash
# ユニットテスト
docker compose -f docker-compose.dev.yml exec collector pytest tests/

# 統合テスト（サンプルログ使用）
docker compose -f docker-compose.dev.yml exec collector pytest tests/integration/

# カバレッジ
docker compose -f docker-compose.dev.yml exec collector pytest --cov=src tests/
```

## 将来の拡張性

1. **複数インスタンス対応**
   - 共有 DB（PostgreSQL）使用
   - Redis でキュー管理

2. **メッセージキュー導入**
   - Kafka/RabbitMQ で信頼性向上
   - バッファリング機能追加

3. **プラグイン機構**
   - カスタムパーサー追加
   - カスタム送信先追加（Elasticsearch 等）

4. **Web UI**
   - 処理状況確認ダッシュボード
   - 設定変更インターフェース
