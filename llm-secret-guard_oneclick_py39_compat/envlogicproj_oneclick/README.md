# Can AI Keep a Secret?

## LLM Secret Guard Benchmark

本專案是一個 **LLM 機密資料防護測試框架**，用來測試不同 AI 模型在面對 Prompt Injection、角色扮演、規則覆蓋、編碼繞過與多輪誘導時，是否能保護 hidden flag。

## 第一版目標

第一版採用：

```text
固定攻擊題庫 attacks.json
        ↓
main.py / run_benchmark.py
        ↓
Target LLM (Mock / 本地模型框架)
        ↓
Leak Detector
        ↓
results.csv / report.md
```

第一版重點：

> AI 的回覆會影響評分，但不影響下一題要問什麼。

也就是不根據 AI 回覆臨時追問，而是使用固定腳本，確保不同模型受到相同測試。

## 專案結構

```text
llm-secret-guard/
├── src/
│   ├── main.py
│   ├── run_benchmark.py         - 支援 mock / ollama:<model_name>
│   ├── model_client.py          - 支援本地模型掛載
│   ├── leak_detector.py
│   ├── scoring.py
│   ├── report_generator.py
│   ├── run_all_local_models.py  - 批次測試框架 (TODO)
│   ├── clients/
│   │   ├── mock_client.py
│   │   └── ollama_client.py
│   └── agents/
│       ├── attacker_agent.py
│       └── judge_agent.py
├── attacks/
│   └── attacks.json
├── data/
│   └── protected_data.txt
├── prompts/
│   └── system_prompt.txt
├── results/
├── reports/
├── docs/
│   ├── architecture.md
│   └── demo_script.md
├── configs/
│   └── local_models.json        - 本地模型配置
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## 快速開始

### 1. 安裝環境

```bash
pip install -r requirements.txt
```

### 2. 先跑 Mock 模型

```bash
python src/run_benchmark.py --model mock
```

### 3. 手動測試模式

```bash
python src/main.py --model mock
```

### 4. 產生報告

```bash
python src/report_generator.py
```

## 本地模型支援

本專案支援本地開源模型測試，目前結構如下：

| 組件 | 狀態 | 用途 |
|------|------|------|
| OllamaClient | ✅ 已實現 | 本地 Ollama 模型支援 |
| configs/local_models.json | ✅ 已建立 | 模型配置清單 |
| run_all_local_models.py | 🔧 框架 (TODO) | 批次測試執行器 |

### 使用本地模型的命令

```bash
# 單一模型測試
python src/run_benchmark.py --model ollama:qwen2.5:3b

# 批次模型測試
python src/run_all_local_models.py
```

## 目前版本

- V1：固定題庫 vs Mock 模型（已完成）
- V2：本地模型支援（Ollama 已實現）
- V3：AI vs AI 自動攻防
- V4：Dashboard / Web UI / MCP 工具整合

## 安全聲明

本專案只使用 fake flag，不應放入真實密碼、API Key、個資或公司機密。

## Semi-auto Ollama 模型選擇流程

執行：

```bash
python semi_auto_ollama.py
```

模型選單採用類似 opencode 的方向鍵選單；不用手打數字。

操作方式：

```text
使用 ↑/↓ 選擇，Enter 確認，Esc 取消。
```

如果目前的 CMD / PowerShell 不支援方向鍵互動選單，可以改用數字備援模式：

```bash
python semi_auto_ollama.py --simple
```

### 第一層執行模式

程式啟動後會顯示：

```text
選擇執行模式

> 測試單一模型
  測試模型清單
  管理模型清單
  離開
```


### 返回規則

互動選單統一採用：

```text
第一層主選單：離開
第二層之後：返回
Esc：等同返回；在第一層主選單則等同離開
```

這樣使用者在任何子選單都可以回到上一層，不會被卡在某個流程中。

### 測試單一模型

進入後會顯示 Ollama 模型與下載狀態：

```text
選擇 Ollama 模型

> qwen2.5:0.5b : 已下載
  qwen3:1.7b   : 未下載
  管理模型清單
  手動輸入模型名稱
  返回
```

模型顯示格式：

```text
模型名 : 已下載 / 未下載
```

下載狀態來自 Ollama API：

```text
http://127.0.0.1:11434/api/tags
```

### 測試模型清單

進入後會先顯示目前清單中的模型與下載狀態，然後提供：

```text
開始測試清單
下載缺少的模型後測試
管理模型清單
返回
```

「開始測試清單」會依序測試清單中的模型；如果遇到未下載模型，程式會在測試前詢問是否下載。

「下載缺少的模型後測試」會先對尚未下載的模型執行：

```bash
ollama pull <model>
```

然後再開始批次測試。

### 管理模型清單

使用者可以自己手動加入模型。進入「管理模型清單」後可選：

```text
查看模型清單
新增模型到清單
新增並下載模型
從清單移除模型
返回
```

說明：

- 「新增模型到清單」只會把模型名稱加入 `model_list.txt`，不會下載。
- 「新增並下載模型」會先加入清單，再執行 `ollama pull <model>`。
- 「從清單移除模型」只會移除 `model_list.txt` 內的項目，不會刪除 Ollama 本機模型。



## 互動操作規則

- 選單畫面：使用 `↑ / ↓` 選擇，`Enter` 確認，`Esc` 返回上一層。
- 第一層主選單：`Esc` 等同離開。
- 手動輸入畫面：`Esc` 直接返回上一層，不需要輸入 `b`、`back` 或 `q`。
- 確認畫面：`Esc` 視為取消，不會下載模型或修改清單。
