# Design Document

## Overview

無線LAN性能調査ツールは、Python を基盤とした包括的なネットワーク性能測定システムです。iperf3、ping、Win32 API を統合して、無線LAN環境の多角的な性能評価を自動化します。測定結果はCSV形式で構造化され、継続的な性能監視と分析を可能にします。

## Architecture

### システム構成

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Application                         │
├─────────────────────────────────────────────────────────────┤
│  Configuration Manager  │  Measurement Orchestrator        │
├─────────────────────────────────────────────────────────────┤
│  WiFi Info    │  Network   │  File Transfer │  Data Export  │
│  Collector    │  Tester    │  Tester        │  Manager      │
├─────────────────────────────────────────────────────────────┤
│  Win32 API    │  iperf3    │  ping          │  CSV Writer   │
│  Interface    │  Client    │  Executor      │               │
└─────────────────────────────────────────────────────────────┘
```

### 技術スタック

- **Python 3.8+**: メインプログラミング言語
- **pywin32**: Win32 API アクセス用ライブラリ
- **pythonping**: 純粋Python実装のpingライブラリ
- **subprocess**: iperf3 コマンド実行
- **csv**: データ出力用標準ライブラリ
- **datetime**: タイムスタンプ管理
- **statistics**: 統計計算用標準ライブラリ
- **configparser**: 設定ファイル管理

## Components and Interfaces

### 1. Configuration Manager

**責務**: アプリケーション設定の管理と検証

```python
class ConfigurationManager:
    def load_config(self, config_file: str) -> dict
    def validate_config(self, config: dict) -> bool
    def get_iperf_server_config(self) -> tuple[str, int]
    def get_measurement_params(self) -> dict
```

**設定項目**:
- iperf3 サーバー情報 (IP アドレス、ポート)
- 測定パラメータ (回数、間隔、タイムアウト)
- デバイス情報 (名前、場所、経路)
- 出力設定 (CSV ファイルパス)

### 2. WiFi Information Collector

**責務**: Win32 API を使用した無線LAN情報の取得

```python
class WiFiInfoCollector:
    def get_rssi(self) -> float
    def get_link_quality(self) -> float
    def get_tx_rate(self) -> float
    def get_current_connection_info(self) -> dict
```

**Win32 API 使用**:
- `WlanOpenHandle`: WLAN ハンドルの取得
- `WlanEnumInterfaces`: 無線インターフェースの列挙
- `WlanQueryInterface`: 接続情報の取得

### 3. Network Performance Tester

**責務**: iperf3 と pythonping を使用したネットワーク性能測定

```python
class NetworkTester:
    def run_tcp_test(self, server: str, port: int, duration: int) -> dict
    def run_udp_test(self, server: str, port: int, duration: int) -> dict
    def run_ping_test(self, target: str, count: int) -> dict
    def parse_iperf_output(self, output: str) -> dict
    def calculate_ping_statistics(self, ping_results) -> dict
```

**測定項目**:
- TCP スループット、再送回数
- UDP ロス率、ジッター
- Ping 平均、最大、標準偏差

**pythonping の利点**:
- 管理者権限不要でのping実行
- 詳細な統計情報の直接取得
- タイムアウトとエラーハンドリングの細かい制御

### 4. File Transfer Tester

**責務**: 実際のファイル転送による性能測定

```python
class FileTransferTester:
    def create_test_file(self, size_mb: int) -> str
    def transfer_file(self, source: str, destination: str) -> dict
    def calculate_transfer_stats(self, transfer_times: list) -> dict
    def cleanup_test_files(self) -> None
```

### 5. Data Export Manager

**責務**: 測定結果のCSV出力管理

```python
class DataExportManager:
    def initialize_csv(self, filepath: str) -> None
    def write_measurement_data(self, data: dict) -> None
    def format_csv_row(self, measurement: dict) -> list
```

**CSV フォーマット**:
```csv
デバイス,場所,経路,Timestamp,RSSI (dBm),Link Quality (%),Tx Rate (Mbps),TCP スループット (Mbps),TCP 再送回数,UDP ロス率 (%),UDP ジッター (ms),ファイル送信 平均速度 (MB/s),ファイル送信 最大揺れ (MB/s),Ping 平均 (ms),Ping 最大 (ms),Ping 標準偏差 (ms),備考
```

### 6. Measurement Orchestrator

**責務**: 全体的な測定フローの制御

```python
class MeasurementOrchestrator:
    def run_full_measurement(self) -> dict
    def run_single_test_cycle(self) -> dict
    def handle_measurement_errors(self, error: Exception) -> str
    def validate_prerequisites(self) -> bool
```

## Data Models

### MeasurementResult

```python
@dataclass
class MeasurementResult:
    device: str
    location: str
    route: str
    timestamp: datetime
    rssi_dbm: Optional[float]
    link_quality_percent: Optional[float]
    tx_rate_mbps: Optional[float]
    tcp_throughput_mbps: Optional[float]
    tcp_retransmissions: Optional[int]
    udp_loss_percent: Optional[float]
    udp_jitter_ms: Optional[float]
    file_transfer_avg_mbps: Optional[float]
    file_transfer_max_variation_mbps: Optional[float]
    ping_avg_ms: Optional[float]
    ping_max_ms: Optional[float]
    ping_stddev_ms: Optional[float]
    notes: str = ""
```

### Configuration

```python
@dataclass
class Configuration:
    iperf_server_ip: str
    iperf_server_port: int = 5201
    device_name: str
    location: str
    route: str
    ping_target: str
    ping_count: int = 10
    iperf_duration: int = 10
    measurement_interval: int = 60
    csv_output_path: str = "wireless_lan_measurements.csv"
```

## Error Handling

### エラー分類と対応

1. **接続エラー**
   - iperf3 サーバー未応答
   - ping ターゲット到達不可
   - 対応: タイムアウト設定、リトライ機能、エラーログ記録

2. **Win32 API エラー**
   - 無線アダプター未検出
   - API 呼び出し失敗
   - 対応: 例外処理、代替値設定、詳細エラーメッセージ

3. **ファイルシステムエラー**
   - CSV ファイル書き込み失敗
   - 一時ファイル作成失敗
   - 対応: 権限確認、ディスク容量チェック、バックアップ機能

### エラーハンドリング戦略

```python
class ErrorHandler:
    def handle_network_error(self, error: Exception) -> str
    def handle_api_error(self, error: Exception) -> str
    def handle_file_error(self, error: Exception) -> str
    def log_error(self, error: Exception, context: str) -> None
```

## Testing Strategy

### 単体テスト

- **WiFiInfoCollector**: モック Win32 API を使用したテスト
- **NetworkTester**: iperf3 出力パース機能テスト、pythonping レスポンス処理テスト
- **DataExportManager**: CSV 出力フォーマットの検証
- **ConfigurationManager**: 設定ファイル読み込み・検証テスト

### 統合テスト

- **End-to-End 測定フロー**: 実際の iperf3 サーバーを使用した完全測定
- **エラーシナリオ**: ネットワーク切断、サーバー停止時の動作確認
- **CSV 出力検証**: 生成されるCSVファイルの完全性確認

### テスト環境要件

- Windows 環境 (Win32 API テスト用)
- iperf3 サーバー (ローカルまたはリモート)
- 無線LAN接続環境
- Python 3.8+ とテスト用ライブラリ (pytest, unittest.mock)

### パフォーマンステスト

- 長時間連続測定での安定性確認
- メモリリーク検出
- CPU 使用率監視
- 大量データ処理時の性能評価