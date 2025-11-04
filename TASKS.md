# TASKS.md

## 現在のステータス

プロジェクト初期セットアップ段階

## タスク一覧

### Phase 1: プロジェクトセットアップ

- [ ] プロジェクト構造作成
  - [ ] ディレクトリ構成作成
  - [ ] pyproject.toml 作成
  - [ ] requirements.txt 作成
  - [ ] .gitignore 作成
  - [ ] README.md 作成

- [ ] 開発環境セットアップ
  - [ ] pre-commit 設定
  - [ ] ruff 設定
  - [ ] mypy 設定
  - [ ] pytest 設定

### Phase 2: コア機能実装

#### 2.1 データモデル実装

- [ ] 設定モデル実装 (models/config.py)
  - [ ] YAML読み込み
  - [ ] バリデーション
  - [ ] デフォルト値設定

- [ ] ログエントリモデル実装 (models/log_entry.py)
  - [ ] TXTログ構造定義
  - [ ] JSON構造定義
  - [ ] 統合データ構造定義

#### 2.2 ログパーサー実装

- [ ] TXTログパーサー (collector/parser.py)
  - [ ] UTF-8 BOM対応
  - [ ] ログレベル抽出 (info/warn/error/debug)
  - [ ] エラーメッセージ抽出
  - [ ] 処理フェーズ判定
  - [ ] 統計情報集計

- [ ] JSONパーサー (collector/parser.py)
  - [ ] JSONファイル読み込み
  - [ ] メタデータ抽出
  - [ ] 番組名抽出
  - [ ] 圧縮率計算

- [ ] 統合データ生成 (collector/parser.py)
  - [ ] TXT + JSON データマージ
  - [ ] ステータス判定 (success/failed/warning)
  - [ ] 重要度判定 (info/warning/critical)
  - [ ] Lokiラベル生成 (service/status/severity/encoder等)

#### 2.3 ログ監視機能実装

- [ ] ファイル監視 (collector/watcher.py)
  - [ ] inotify (watchdog) セットアップ
  - [ ] JSONファイル作成検知
  - [ ] 対応TXTファイル待機
  - [ ] ファイルペア関連付け
  - [ ] 処理キュー管理

#### 2.4 ログ送信機能実装

- [ ] Vector送信 (collector/sender.py)
  - [ ] HTTP POST 実装
  - [ ] JSON シリアライズ
  - [ ] タイムアウト処理
  - [ ] エラーハンドリング

- [ ] rsyslogd送信 (collector/sender.py)
  - [ ] syslog プロトコル実装
  - [ ] facility/severity マッピング
  - [ ] CRITICAL判定ロジック
  - [ ] メッセージフォーマット

- [ ] 送信済み管理 (collector/database.py)
  - [ ] SQLite DB初期化
  - [ ] 送信済み記録
  - [ ] 重複チェック
  - [ ] リトライ管理

- [ ] リトライロジック (collector/sender.py)
  - [ ] exponential backoff 実装
  - [ ] 最大リトライ回数制御
  - [ ] 失敗ログ記録

#### 2.5 メインアプリケーション

- [ ] アプリケーションエントリーポイント (main.py)
  - [ ] 設定読み込み
  - [ ] ロギングセットアップ
  - [ ] 各コンポーネント初期化
  - [ ] メインループ実装
  - [ ] シグナルハンドリング (SIGTERM/SIGINT)

- [ ] ヘルスチェックエンドポイント
  - [ ] HTTP サーバー起動
  - [ ] /health エンドポイント実装
  - [ ] メトリクス収集

### Phase 3: テスト実装

- [ ] ユニットテスト
  - [ ] test_parser.py
    - [ ] TXTパーサーテスト
    - [ ] JSONパーサーテスト
    - [ ] 統合データ生成テスト
  - [ ] test_sender.py
    - [ ] Vector送信テスト (mock)
    - [ ] syslog送信テスト (mock)
    - [ ] リトライロジックテスト
  - [ ] test_database.py
    - [ ] DB操作テスト
    - [ ] 重複チェックテスト

- [ ] 統合テスト
  - [ ] エンドツーエンドテスト
    - [ ] サンプルログファイル使用
    - [ ] 全フロー動作確認

### Phase 4: Docker環境構築

- [ ] Dockerfile作成
  - [ ] Python 3.11+ ベースイメージ
  - [ ] 依存パッケージインストール
  - [ ] アプリケーション配置
  - [ ] エントリーポイント設定

- [ ] docker-compose.yml作成（本番用）
  - [ ] amatsukaze-log-collector サービス
  - [ ] ボリュームマウント設定
  - [ ] ネットワーク設定
  - [ ] 環境変数設定

- [ ] docker-compose.dev.yml作成（開発用）
  - [ ] collector サービス設定
  - [ ] rsyslogd サービス追加
  - [ ] Vector サービス追加
  - [ ] Loki サービス追加
  - [ ] Grafana サービス追加
  - [ ] ホットリロード設定
  - [ ] デバッグポート公開
  - [ ] サンプルログマウント

- [ ] 設定ファイル作成
  - [ ] config/rsyslog.conf
  - [ ] config/vector.toml
  - [ ] config/loki.yaml

- [ ] 動作確認
  - [ ] docker-compose.dev.yml で環境起動
  - [ ] サンプルログ使用した動作確認
  - [ ] Grafanaでログ表示確認

### Phase 5: ドキュメント整備

- [ ] README.md
  - [ ] プロジェクト概要
  - [ ] クイックスタート
  - [ ] 設定ガイド
  - [ ] トラブルシューティング

- [ ] docs/setup.md
  - [ ] 詳細セットアップ手順
  - [ ] rsyslogd/Vector/Loki 連携設定
  - [ ] 環境変数一覧

- [ ] docs/api.md
  - [ ] ヘルスチェックAPI仕様
  - [ ] 内部API仕様

- [ ] config/config.example.yaml
  - [ ] 設定例作成
  - [ ] コメント追加

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

## 次のアクション

Phase 1: プロジェクトセットアップから開始

## 備考

- Phase 2-3 を優先実装（コア機能とテスト）
- Phase 4-5 は並行実施可能
- Phase 6-7 は動作確認後に実施
- 各フェーズ完了後、本ファイルを更新
