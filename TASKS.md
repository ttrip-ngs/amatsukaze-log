# TASKS.md

## 現在のステータス

Phase 5: ドキュメント整備進行中
- Phase 1: プロジェクトセットアップ完了
- Phase 2.1: データモデル実装完了
- Phase 2.2: ログパーサー実装完了（YAMLベースのカスタムルールシステム含む）
- Phase 2.3: ログ監視機能実装完了
- Phase 2.4: ログ書き込み機能実装完了（ファイルベース方式）
- Phase 2.5: メインアプリケーション実装完了
- Phase 4: Docker環境構築完了（動作確認済み）
- Phase 3: ユニットテスト完了（55テスト、75%カバレッジ）
- Phase 5: ドキュメント整備進行中
- 次: 統合テスト作成、Phase 6 Grafana連携

## タスク一覧

### Phase 1: プロジェクトセットアップ ✅

- [x] プロジェクト構造作成
  - [x] ディレクトリ構成作成
  - [x] pyproject.toml 作成
  - [x] ~~requirements.txt 作成~~ (pyproject.tomlに統一)
  - [x] .gitignore 作成
  - [x] README.md 作成

- [x] 開発環境セットアップ
  - [x] pre-commit 設定
  - [x] ruff 設定
  - [x] mypy 設定
  - [x] pytest 設定

### Phase 2: コア機能実装

#### 2.1 データモデル実装 ✅

- [x] 設定モデル実装 (models/config.py)
  - [x] YAML読み込み
  - [x] バリデーション
  - [x] デフォルト値設定
  - [x] CriticalRuleモデル追加（YAMLカスタムルール）

- [x] ログエントリモデル実装 (models/log_entry.py)
  - [x] TXTログ構造定義
  - [x] JSON構造定義
  - [x] 統合データ構造定義
  - [x] AudioDiffモデルのJSON alias対応

#### 2.2 ログパーサー実装 ✅

- [x] TXTログパーサー (collector/parser.py)
  - [x] UTF-8 BOM対応
  - [x] ログレベル抽出 (info/warn/error/debug)
  - [x] エラーメッセージ抽出
  - [x] 処理フェーズ判定
  - [x] 統計情報集計
  - [x] YAMLパターンルールによるCRITICAL判定

- [x] JSONパーサー (collector/parser.py)
  - [x] JSONファイル読み込み
  - [x] メタデータ抽出
  - [x] 番組名抽出
  - [x] 圧縮率計算

- [x] 統合データ生成 (collector/parser.py)
  - [x] TXT + JSON データマージ
  - [x] ステータス判定 (success/failed/warning)
  - [x] 重要度判定 (info/warning/critical)
  - [x] Lokiラベル生成 (service/status/severity/encoder等)
  - [x] YAML条件式ルールによるCRITICAL判定

- [x] 条件式評価器実装 (utils/condition_evaluator.py)
  - [x] simpleeval導入で安全な式評価
  - [x] ドット記法サポート (audiodiff.maxdiff等)
  - [x] 複雑な論理式サポート (括弧、not演算子)

#### 2.3 ログ監視機能実装 ✅

- [x] ファイル監視 (collector/watcher.py)
  - [x] inotify (watchdog) セットアップ
  - [x] JSONファイル作成検知
  - [x] 対応TXTファイル待機
  - [x] ファイルペア関連付け
  - [x] 処理キュー管理（スレッドベース）

#### 2.4 ログ書き込み機能実装 ✅

- [x] ファイルベース方式に変更（HTTP送信からの変更）
  - [x] Vector用ログファイル書き込み (collector/writer.py)
    - [x] JSON Lines形式でファイル出力
    - [x] ローテーション機能
  - [x] rsyslogd用ログファイル書き込み (collector/writer.py)
    - [x] syslog形式でファイル出力
    - [x] CRITICALログのみ出力
    - [x] RFC 3164形式対応
  - [x] 統合ライター (collector/writer.py)
    - [x] Vector/Syslog両方への書き込み統合

- [x] 処理済みログ管理 (collector/database.py)
  - [x] SQLite DB初期化
  - [x] 処理済み記録
  - [x] 重複チェック
  - [x] ファイルパストラッキング

#### 2.5 メインアプリケーション ✅

- [x] アプリケーションエントリーポイント (src/main.py)
  - [x] 設定読み込み (YAML)
  - [x] ロギングセットアップ (JSON/テキスト形式)
  - [x] 各コンポーネント初期化
  - [x] メインループ実装
  - [x] シグナルハンドリング (SIGTERM/SIGINT)
  - [x] パス検証とディレクトリ自動作成

- [ ] ヘルスチェックエンドポイント（オプション機能）
  - [ ] HTTP サーバー起動
  - [ ] /health エンドポイント実装
  - [ ] メトリクス収集

### Phase 3: テスト実装 (進行中: 75%カバレッジ)

- [x] ユニットテスト
  - [x] test_parser.py (11テスト)
    - [x] TXTパーサーテスト
    - [x] JSONパーサーテスト
    - [x] 統合データ生成テスト
    - [x] CRITICALルール対応
  - [x] test_writer.py (9テスト)
    - [x] Vector用ファイル出力テスト
    - [x] Syslog用ファイル出力テスト
    - [x] ローテーションテスト
  - [x] test_database.py (8テスト)
    - [x] DB操作テスト
    - [x] 重複チェックテスト
  - [x] test_watcher.py (7テスト)
    - [x] ファイル監視テスト
    - [x] タイムアウトテスト
  - [x] test_condition_evaluator.py (19テスト)
    - [x] 条件式評価テスト
    - [x] ドット記法テスト
  - [x] conftest.py (共通フィクスチャ)

- [ ] 統合テスト
  - [ ] エンドツーエンドテスト
    - [ ] サンプルログファイル使用
    - [ ] 全フロー動作確認

### Phase 4: Docker環境構築 ✅

- [x] Dockerfile作成
  - [x] Python 3.13-slim ベースイメージ
  - [x] 依存パッケージインストール
  - [x] アプリケーション配置
  - [x] エントリーポイント設定

- [x] docker-compose.yml作成（本番用）
  - [x] amatsukaze-log-collector サービス
  - [x] ボリュームマウント設定
  - [x] ネットワーク設定
  - [x] 環境変数設定

- [x] docker-compose.dev.yml作成（開発用）
  - [x] collector サービス設定
  - [x] rsyslogd サービス追加
  - [x] Vector サービス追加
  - [x] ~~Loki サービス追加~~ (外部サーバー使用)
  - [x] ~~Grafana サービス追加~~ (外部サーバー使用)
  - [x] ホットリロード設定
  - [x] デバッグポート公開
  - [x] サンプルログマウント

- [x] 設定ファイル作成
  - [x] config/rsyslog.conf
  - [x] config/vector.toml
  - [x] ~~config/loki.yaml~~ (外部サーバー使用)

- [x] 動作確認
  - [x] docker-compose.dev.yml で環境起動
  - [x] サンプルログ使用した動作確認
  - [ ] Grafanaでログ表示確認（外部サーバー接続後）

### Phase 5: ドキュメント整備 (進行中)

- [x] README.md
  - [x] プロジェクト概要
  - [x] クイックスタート
  - [x] 設定ガイド
  - [x] CRITICALルール説明
  - [x] テスト状況

- [x] docs/setup.md
  - [x] 詳細セットアップ手順
  - [x] rsyslogd/Vector/Loki 連携設定
  - [x] 環境変数一覧
  - [x] トラブルシューティング

- [ ] docs/api.md（オプション）
  - [ ] ヘルスチェックAPI仕様
  - [ ] 内部API仕様

- [x] config/config.example.yaml
  - [x] 設定例作成
  - [x] 詳細コメント追加

### Phase 6: Grafana連携

- [ ] Vector設定作成 (config/vector.toml)
  - [ ] source 設定
  - [ ] transform 設定
  - [ ] sink (Loki) 設定

- [ ] Grafanaダッシュボード雛形 (grafana/dashboards/amatsukaze.json)
  - [ ] エンコードタスク一覧パネル
  - [ ] エラー詳細パネル
  - [ ] 統計パネル
  - [ ] 変数設定（時間範囲、ステータスフィルタ等）

### Phase 7: 本番デプロイ準備

- [ ] 本番環境設定
  - [ ] config.yaml 本番用設定
  - [ ] ログレベル調整
  - [ ] リトライパラメータ調整

- [ ] 監視設定
  - [ ] Zabbix item 設定
  - [ ] アラート閾値設定

- [ ] 運用ドキュメント
  - [ ] デプロイ手順
  - [ ] トラブルシューティング
  - [ ] ログローテーション設定

## 完了したタスク

- [x] 要件定義とアーキテクチャ設計の確認
- [x] CLAUDE.md 作成
- [x] docs/architecture.md 作成
- [x] TASKS.md 作成（本ファイル）
- [x] Phase 1: プロジェクトセットアップ完了
- [x] Phase 2: コア機能実装完了
  - [x] Phase 2.1: データモデル実装完了
  - [x] Phase 2.2: ログパーサー実装完了
    - [x] YAMLベースのカスタムCRITICALルールシステム実装
    - [x] simpleeval導入で安全性向上
    - [x] Python 3.12+対応、全ライブラリ最新化
  - [x] Phase 2.3: ログ監視機能実装完了（watchdog）
  - [x] Phase 2.4: ログ書き込み機能実装完了（ファイルベース方式）
  - [x] Phase 2.5: メインアプリケーション実装完了
- [x] Phase 4: Docker環境構築完了
  - [x] Dockerfile作成（Python 3.13-slim）
  - [x] docker-compose.yml / docker-compose.dev.yml作成
  - [x] Vector/rsyslog設定ファイル作成
  - [x] 動作確認完了（ファイル検出 → パース → Vector出力）
  - [x] バグ修正: SQLiteスレッドセーフ対応
  - [x] バグ修正: main.pyのパーサー呼び出し修正
- [x] Phase 3: テスト拡充（ユニットテスト完了）
  - [x] test_parser.py (11テスト、91%カバレッジ)
  - [x] test_writer.py (9テスト、85%カバレッジ)
  - [x] test_database.py (8テスト、100%カバレッジ)
  - [x] test_watcher.py (7テスト、85%カバレッジ)
  - [x] test_condition_evaluator.py (19テスト、100%カバレッジ)
  - [x] conftest.py 共通フィクスチャ作成
  - [x] Pydantic V2 ConfigDict移行（警告解消）
  - [x] CRITICALルールテスト対応
- [x] Phase 5: ドキュメント整備（主要完了）
  - [x] README.md 更新（アーキテクチャ、設定ガイド、テスト状況）
  - [x] config/config.example.yaml 作成（詳細コメント付き）
  - [x] docs/setup.md 作成（セットアップガイド、トラブルシューティング）

## 次のアクション

Phase 3: 統合テスト追加、Phase 6: Grafana連携

推奨:
1. 統合テスト（エンドツーエンドテスト）を追加してカバレッジ向上
2. Phase 6 Grafana連携（ダッシュボード雛形作成）
3. 外部Loki/Grafanaサーバー接続テスト

## 備考

- Phase 2-3 を優先実装（コア機能とテスト）
- Phase 4-5 は並行実施可能
- Phase 6-7 は動作確認後に実施
- 各フェーズ完了後、本ファイルを更新
