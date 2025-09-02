# Windows Setup Guide

## Windows環境でのセットアップガイド

### 前提条件

1. **Python 3.8以上**がインストールされていること
2. **管理者権限**でコマンドプロンプトまたはPowerShellを実行できること
3. WiFiアダプターが有効になっていること

### インストール手順

1. **リポジトリのクローン**
```powershell
git clone https://github.com/TakashiAihara/wlan-scanner.git
cd wlan-scanner
```

2. **依存関係のインストール**
```powershell
pip install -r requirements.txt
```

### Windows特有の設定

#### 1. WiFiインターフェース名の確認

PowerShellまたはコマンドプロンプトで以下を実行：

```powershell
netsh wlan show interfaces
```

出力例：
```
名前                   : Wi-Fi
説明                   : Intel(R) Wi-Fi 6 AX200 160MHz
GUID                   : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
物理アドレス           : XX:XX:XX:XX:XX:XX
状態                   : 接続されました
```

「名前」の値（例：`Wi-Fi`）を設定ファイルで使用します。

#### 2. 設定ファイルの作成

Windows用の設定ファイルをコピー：

```powershell
copy config\windows.ini config\config.ini
```

`config\config.ini`を編集して、WiFiインターフェース名を設定：

```ini
[network]
interface_name = Wi-Fi  # 上記で確認した名前を設定
```

### 実行方法

**必ず管理者権限で実行してください**

1. **PowerShellを管理者として実行**
   - Windowsキー + X → Windows PowerShell (管理者)

2. **アプリケーションの実行**
```powershell
python main.py
```

### トラブルシューティング

#### エンコーディングエラー

症状：
```
UnicodeDecodeError: 'cp932' codec can't decode byte...
```

解決方法：
このエラーは修正済みですが、もし発生する場合は以下を試してください：

1. PowerShellの文字エンコーディングを確認：
```powershell
[System.Console]::OutputEncoding
```

2. UTF-8に設定：
```powershell
[System.Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
```

#### Permission Denied エラー

症状：
```
[Errno 1] Operation not permitted
```

解決方法：
管理者権限でPowerShellまたはコマンドプロンプトを実行してください。

#### WiFiアダプターが見つからない

症状：
```
WiFi interface is not connected
```

解決方法：

1. WiFiが有効になっているか確認：
```powershell
netsh wlan show interfaces
```

2. 有線接続のみの場合は、`--tests`オプションでWiFi以外のテストを実行：
```powershell
python main.py --tests ping,iperf_tcp
```

#### pythonpingモジュールエラー

症状：
```
ModuleNotFoundError: No module named 'pythonping'
```

解決方法：
```powershell
pip install pythonping --upgrade
```

### Windows Defenderファイアウォールの設定

iPerf3を使用する場合、ファイアウォールで許可が必要な場合があります：

1. Windows Defender ファイアウォールを開く
2. 「詳細設定」をクリック
3. 「受信の規則」→「新しい規則」
4. ポート5201（iPerf3のデフォルト）を許可

### 推奨事項

1. **定期実行にはタスクスケジューラを使用**
   - 管理者権限で実行するタスクを作成
   - トリガーで実行間隔を設定

2. **ログファイルの確認**
```powershell
python main.py --log-file scanner.log --log-level DEBUG
```

3. **出力ディレクトリの確認**
   - デフォルトでは`data`フォルダにCSVファイルが保存されます
   - Excelで開く際は、UTF-8エンコーディングを指定してください

### サンプル実行コマンド

```powershell
# 基本的な実行
python main.py

# 5分間隔で連続測定
python main.py --continuous -i 300

# 特定のテストのみ実行
python main.py --tests ping,wifi_info

# デバッグモード
python main.py -v --log-level DEBUG

# 設定の検証のみ
python main.py --dry-run
```

### 注意事項

- Windows環境では、WiFiアダプター名が日本語の場合があります（例：「ワイヤレス ネットワーク接続」）
- 一部のアンチウイルスソフトがping操作をブロックする場合があります
- VPN接続中は正確な測定ができない場合があります