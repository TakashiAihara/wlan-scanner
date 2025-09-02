# Requirements Document

## Introduction

このプロジェクトは、Python を使用して無線LAN環境の性能を包括的に調査・記録するツールを開発することを目的としています。iperf3、ping、Win32 APIを活用して、RSSI、スループット、遅延、パケットロスなどの重要な無線LAN性能指標を測定し、CSV形式で記録します。

## Requirements

### Requirement 1

**User Story:** システム管理者として、無線LAN環境の性能データを自動的に収集したいので、手動での測定作業を削減し、一貫性のあるデータを取得できる

#### Acceptance Criteria

1. WHEN ツールが実行されるとき THEN システムは iperf3 サーバーへの接続を確認し、利用可能であることを検証する SHALL
2. WHEN 測定が開始されるとき THEN システムは Win32 API を使用して RSSI (dBm)、Link Quality (%)、Tx Rate (Mbps) を取得する SHALL
3. WHEN iperf3 測定が実行されるとき THEN システムは TCP スループット (Mbps) と TCP 再送回数を記録する SHALL
4. WHEN UDP 測定が実行されるとき THEN システムは UDP ロス率 (%) と UDP ジッター (ms) を記録する SHALL

### Requirement 2

**User Story:** ネットワーク技術者として、ファイル転送性能を測定したいので、実際の使用環境での転送速度の変動を把握できる

#### Acceptance Criteria

1. WHEN ファイル送信テストが実行されるとき THEN システムはファイル送信の平均速度 (MB/s) を計算する SHALL
2. WHEN ファイル送信テストが実行されるとき THEN システムはファイル送信の最大揺れ (MB/s) を記録する SHALL
3. WHEN 測定中にエラーが発生したとき THEN システムは備考欄にエラー情報を記録する SHALL

### Requirement 3

**User Story:** ネットワーク管理者として、ping による遅延測定を行いたいので、ネットワークの応答性能を評価できる

#### Acceptance Criteria

1. WHEN ping 測定が実行されるとき THEN システムは複数回の ping を実行し、平均遅延 (ms) を計算する SHALL
2. WHEN ping 測定が実行されるとき THEN システムは最大遅延 (ms) を記録する SHALL
3. WHEN ping 測定が実行されるとき THEN システムは遅延の標準偏差 (ms) を計算する SHALL

### Requirement 4

**User Story:** データ分析者として、測定結果をCSV形式で保存したいので、後でデータ分析や可視化を行うことができる

#### Acceptance Criteria

1. WHEN 測定が完了するとき THEN システムは結果を指定されたCSV形式で保存する SHALL
2. WHEN CSV ファイルが作成されるとき THEN ヘッダーは "デバイス","場所","経路","Timestamp","RSSI (dBm)","Link Quality (%)","Tx Rate (Mbps)","TCP スループット (Mbps)","TCP 再送回数","UDP ロス率 (%)","UDP ジッター (ms)","ファイル送信 平均速度 (MB/s)","ファイル送信 最大揺れ (MB/s)","Ping 平均 (ms)","Ping 最大 (ms)","Ping 標準偏差 (ms)","備考" を含む SHALL
3. WHEN データが記録されるとき THEN 各測定にはタイムスタンプが自動的に付与される SHALL

### Requirement 5

**User Story:** システム運用者として、測定設定をカスタマイズしたいので、異なる環境や要件に応じて測定パラメータを調整できる

#### Acceptance Criteria

1. WHEN ツールが起動するとき THEN ユーザーはデバイス名、場所、経路を指定できる SHALL
2. WHEN 設定が変更されるとき THEN システムは iperf3 サーバーのアドレスとポートを設定できる SHALL
3. WHEN 測定が実行されるとき THEN システムは測定回数や間隔を設定可能にする SHALL

### Requirement 6

**User Story:** トラブルシューティング担当者として、エラーハンドリングと診断情報を取得したいので、測定失敗時の原因を特定できる

#### Acceptance Criteria

1. WHEN iperf3 サーバーに接続できないとき THEN システムは適切なエラーメッセージを表示し、備考欄に記録する SHALL
2. WHEN Win32 API の呼び出しが失敗するとき THEN システムはエラーを処理し、利用可能なデータのみを記録する SHALL
3. WHEN ping が失敗するとき THEN システムはタイムアウトやネットワークエラーを適切に処理する SHALL