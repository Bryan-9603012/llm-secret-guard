# 常見問題排除

## 找不到 Python

請安裝 Python 3.9 或更新版本，安裝時勾選 Add Python to PATH。

## 找不到 Ollama

請先安裝 Ollama，安裝後重新開 CMD，再執行：

```bat
ollama --version
```

## Ollama 連線失敗

先開另一個終端機執行：

```bat
ollama serve
```

或者直接雙擊 `START_HERE.bat`，它會嘗試自動啟動 Ollama。

## 模型未下載

執行：

```bat
ollama pull qwen2.5:0.5b
```

或在工具中選「管理模型清單 → 新增並下載模型」。

## 方向鍵選單異常

改用數字選單：

```bat
python llm_secret_guard.py --simple
```

## 報告沒有產生

請確認：

1. Ollama 已啟動
2. 模型已下載
3. `attacks/` 內有 JSON 攻擊資料集
4. `reports/`、`results/` 資料夾可以寫入
