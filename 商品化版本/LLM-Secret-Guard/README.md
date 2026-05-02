# LLM Secret Guard

**LLM Secret Guard** 是一個給一般使用者操作的本地 LLM 安全測試工具。它會透過 Ollama 測試模型在 prompt injection / secret leakage 類攻擊下是否容易洩漏受保護資訊，並自動輸出報告。

## 一般使用者怎麼開始

1. 先安裝 **Python 3.9+**。
2. 先安裝 **Ollama**。
3. 下載至少一個模型，例如：

```bat
ollama pull qwen2.5:0.5b
```

4. 雙擊：

```text
START_HERE.bat
```

程式會自動建立 `.venv`、安裝需要的 Python 套件、嘗試啟動 Ollama，然後進入互動式選單。

## 主功能

```text
選擇執行模式

> 測試單一模型
  測試模型清單
  管理模型清單
  離開
```

- **測試單一模型**：選一個 Ollama 模型測試。
- **測試模型清單**：依序測試 `model_list.txt` 內的模型。
- **管理模型清單**：新增模型、下載模型、從清單移除模型。
- **Esc**：子選單返回上一層，主選單離開。

## 產出位置

| 位置 | 用途 |
|---|---|
| `reports/` | Markdown 報告與 session summary |
| `results/` | CSV 原始測試結果 |
| `logs/` | 每次執行摘要與除錯資料 |

也可以雙擊：

```text
OPEN_REPORTS.bat
```

快速開啟報告資料夾。

## 注意事項

- 本工具只測試你本機 Ollama 模型，不會把 prompt 或結果送到雲端 API。
- 請只在你有權測試的模型、資料與環境上使用。
- 目前定位是 **consumer-release prototype**，已適合展示與一般操作，但還不是完整商業級 installer。

## If nothing appears when double-clicking

Please extract the ZIP first. Do not run `START_HERE.bat` directly inside the compressed ZIP window.

Recommended launch file:

```bat
START_HERE.cmd
```

The launcher keeps the CMD window open and writes debug details to:

```text
logs/launcher_debug.log
```


## Windows launcher note

The launchers are ASCII-only `.bat/.cmd` files to avoid mojibake on Traditional Chinese Windows CMD.
Use `START_HERE.bat` after extracting the ZIP. Do not run it directly inside the ZIP viewer.
If the window still closes, run `OPEN_DEBUG_WINDOW.cmd` and then type `START_HERE_SAFE.cmd`.
