# 使用者手冊

## 1. 啟動

雙擊 `START_HERE.bat`。

第一次啟動會自動：

1. 建立 `.venv`
2. 安裝 requirements
3. 檢查 Ollama
4. 開啟 LLM Secret Guard 主選單

## 2. 操作方式

方向鍵選擇，Enter 確認，Esc 返回。

如果方向鍵選單在舊 CMD 異常，可以使用：

```bat
python llm_secret_guard.py --simple
```

## 3. 管理模型清單

進入：

```text
管理模型清單
```

可選：

```text
查看模型清單
新增模型到清單
新增並下載模型
從清單移除模型
返回
```

「從清單移除模型」只會移除 `model_list.txt` 的項目，不會刪除 Ollama 本機模型。

## 4. 測試模型清單

如果清單中有未下載模型：

- 選「開始測試清單」：未下載模型會被略過或詢問。
- 選「下載缺少的模型後測試」：會先 `ollama pull`，再開始測試。

## 5. 報告

測試完成後查看：

```text
reports/
results/
logs/
```

每次 session 會產生 session summary，方便展示與追蹤。
