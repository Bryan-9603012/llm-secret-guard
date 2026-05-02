# Attack Datasets

本專案現在保留三種 attacks 檔案：

| 檔案 | attack case 數 | 用途 |
|---|---:|---|
| `attacks/attacks.json` | 原始版 | 保留舊 benchmark baseline，不覆蓋 |
| `attacks/attacks_020_balanced.json` | 20 | 每個攻擊類別 1 筆，適合快速 smoke test |
| `attacks/attacks_100_balanced.json` | 100 | 每個攻擊類別 5 筆，適合正式比較 |

注意：`multi_turn_probe` 每個 attack case 會產生多個 turn row，所以「attack case 數」不一定等於最後 CSV 的 sample row 數。

## CLI 用法

```bash
python3 src/run_benchmark.py \
  --model ollama:qwen2.5:7b \
  --ollama-url http://127.0.0.1:11434 \
  --attacks attacks/attacks_100_balanced.json

python3 src/report_generator.py
python3 src/plot_benchmark.py
```

## 半自動流程

```bash
python3 semi_auto_ollama.py
```

流程會要求你選擇 attacks 檔案，預設推薦 `attacks_100_balanced.json`。
