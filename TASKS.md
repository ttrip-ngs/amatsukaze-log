# TASKS.md

## 現在のステータス

Phase 2: コア機能実装中
- Phase 1: プロジェクトセットアップ完了
- Phase 2.1: データモデル実装完了
- Phase 2.2: ログパーサー実装完了（YAMLベースのカスタムルールシステム含む）
- 次: Phase 2.3 ログ監視機能実装

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
- [x] Phase 1: プロジェクトセットアップ完了
- [x] Phase 2.1: データモデル実装完了
- [x] Phase 2.2: ログパーサー実装完了
  - [x] YAMLベースのカスタムCRITICALルールシステム実装
  - [x] simpleeval導入で安全性向上
  - [x] Python 3.12+対応、全ライブラリ最新化

## 次のアクション

Phase 2.3: ログ監視機能実装（watchdogによるファイル監視）

## 備考

- Phase 2-3 を優先実装（コア機能とテスト）
- Phase 4-5 は並行実施可能
- Phase 6-7 は動作確認後に実施
- 各フェーズ完了後、本ファイルを更新
