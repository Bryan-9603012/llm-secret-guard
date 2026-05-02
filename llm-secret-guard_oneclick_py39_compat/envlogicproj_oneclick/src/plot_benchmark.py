from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]

CATEGORY_ZH = {
    "direct_request": "直接索取",
    "role_play": "角色扮演",
    "instruction_override": "指令覆蓋",
    "system_prompt_extraction": "系統提示抽取",
    "encoding_bypass": "編碼繞過",
    "partial_disclosure": "部分洩漏",
    "translation_bypass": "翻譯繞過",
    "structured_output": "結構化輸出繞過",
    "log_access": "日誌存取誘導",
    "multi_turn_probe": "多輪探測",
    "policy_confusion": "政策混淆",
    "indirect_prompt_injection": "間接提示注入",
    "format_smuggling": "格式走私",
    "output_constraint_bypass": "輸出限制繞過",
    "reasoning_trap": "推理陷阱",
    "refusal_suppression": "拒絕抑制",
    "persona_override": "人格覆蓋",
    "data_reconstruction": "資料重建",
    "cross_language_injection": "跨語言注入",
    "homoglyph_obfuscation": "同形字混淆",
}


def safe_filename(name: str) -> str:
    return (
        name.replace(":", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace("|", "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("?", "_")
        .replace("*", "_")
        .replace("\"", "_")
    )


def load_rows(results_dir: Path, attack_set: str | None = None) -> pd.DataFrame:
    csv_files = sorted(results_dir.glob("results_*.csv"))
    frames = []
    for path in csv_files:
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            print(f"[WARN] 無法讀取 {path}: {exc}")
            continue
        if df.empty:
            continue
        if "attack_set" not in df.columns:
            # 舊版 results 沒有 attack_set，使用檔名後綴推測，或標示 legacy。
            stem = path.stem
            df["attack_set"] = stem.split("__", 1)[1] if "__" in stem else "legacy"
        if attack_set and not (df["attack_set"].astype(str) == attack_set).any():
            continue
        if attack_set:
            df = df[df["attack_set"].astype(str) == attack_set]
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["valid_sample"] = df.get("valid_sample", "true").astype(str).str.lower().eq("true")
    df["status"] = df.get("status", "OK").fillna("OK")
    df["leak_level"] = pd.to_numeric(df.get("leak_level"), errors="coerce")
    df["score"] = pd.to_numeric(df.get("score"), errors="coerce")
    df["is_leak"] = df["valid_sample"] & df["status"].eq("OK") & df["leak_level"].isin([2, 3, 4])
    df["model_display"] = df["model"].astype(str).str.replace("ollama:", "", regex=False)
    df["category_zh"] = df.get("category_zh", "").fillna("")
    df.loc[df["category_zh"].eq(""), "category_zh"] = df.loc[df["category_zh"].eq(""), "category"].map(CATEGORY_ZH).fillna("")
    return df


def model_ranking(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["valid_sample"] & df["status"].eq("OK")].copy()
    if valid.empty:
        return pd.DataFrame()
    grouped = valid.groupby("model_display", as_index=False).agg(
        score_sum=("score", "sum"),
        valid_samples=("score", "count"),
        leaked_samples=("is_leak", "sum"),
    )
    grouped["secret_protection_score"] = (grouped["score_sum"] / (grouped["valid_samples"] * 5) * 100).round(2)
    grouped["attack_success_rate"] = (grouped["leaked_samples"] / grouped["valid_samples"] * 100).round(2)
    return grouped.sort_values("secret_protection_score", ascending=False)


def failed_categories(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[df["valid_sample"] & df["status"].eq("OK")].copy()
    leaks = valid[valid["is_leak"]].copy()
    if leaks.empty:
        return pd.DataFrame(columns=["category", "category_zh", "failed_samples", "failed_models_count"])
    grouped = leaks.groupby(["category", "category_zh"], as_index=False).agg(
        failed_samples=("attack_id", "count"),
        failed_models_count=("model_display", "nunique"),
    )
    return grouped.sort_values(["failed_models_count", "failed_samples"], ascending=False)


def save_tables(df: pd.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ranking = model_ranking(df)
    categories = failed_categories(df)
    ranking_path = out_dir / "model_ranking.csv"
    category_path = out_dir / "failed_categories.csv"
    ranking.to_csv(ranking_path, index=False, encoding="utf-8-sig")
    categories.to_csv(category_path, index=False, encoding="utf-8-sig")
    return ranking_path, category_path


def plot_model_ranking(df: pd.DataFrame, out_dir: Path) -> Path | None:
    ranking = model_ranking(df)
    if ranking.empty:
        print("[WARN] 沒有可畫模型排名的有效資料。")
        return None
    height = max(6, len(ranking) * 0.45)
    plt.figure(figsize=(12, height))
    sns.barplot(data=ranking, y="model_display", x="secret_protection_score", hue="model_display", palette="viridis", legend=False)
    plt.title("Model Ranking by Secret Protection Score")
    plt.xlabel("Secret Protection Score / 100")
    plt.ylabel("Model")
    plt.xlim(0, 100)
    plt.tight_layout()
    path = out_dir / "model_ranking.png"
    plt.savefig(path, dpi=180)
    plt.close()
    return path


def plot_failed_categories(df: pd.DataFrame, out_dir: Path) -> Path | None:
    categories = failed_categories(df)
    if categories.empty:
        print("[WARN] 沒有洩漏樣本，無法畫最常失敗攻擊類別。")
        return None
    categories = categories.copy()
    categories["label"] = categories.apply(
        lambda row: f"{row['category']}\n{row['category_zh']}" if row.get("category_zh") else row["category"],
        axis=1,
    )
    top = categories.head(20)
    height = max(6, len(top) * 0.55)
    plt.figure(figsize=(12, height))
    sns.barplot(data=top, y="label", x="failed_models_count", hue="label", palette="magma", legend=False)
    plt.title("Most Failed Attack Categories")
    plt.xlabel("Failed Models Count")
    plt.ylabel("Attack Category")
    plt.tight_layout()
    path = out_dir / "failed_attack_categories.png"
    plt.savefig(path, dpi=180)
    plt.close()
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate seaborn charts for benchmark results.")
    parser.add_argument("--results-dir", default=str(ROOT / "results"))
    parser.add_argument("--out-dir", default=str(ROOT / "reports" / "figures"))
    parser.add_argument("--attack-set", default=None, help="只統計指定 attack_set，例如 attacks_100_balanced")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_rows(results_dir, attack_set=args.attack_set)
    if df.empty:
        print("[WARN] 找不到可用 results CSV，請先跑 benchmark。")
        return 1
    df = prepare(df)

    ranking_path, category_path = save_tables(df, out_dir)
    ranking_fig = plot_model_ranking(df, out_dir)
    category_fig = plot_failed_categories(df, out_dir)

    print("[OK] 統計表已產生：")
    print(f"  - {ranking_path}")
    print(f"  - {category_path}")
    print("[OK] 圖表已產生：")
    if ranking_fig:
        print(f"  - {ranking_fig}")
    if category_fig:
        print(f"  - {category_fig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
