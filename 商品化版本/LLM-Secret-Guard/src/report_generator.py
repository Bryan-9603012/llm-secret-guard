import csv
from collections import Counter, defaultdict
from pathlib import Path

from scoring import calculate_total_score, is_valid_sample


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def generate_report(rows: list[dict], output_path: Path):
    if not rows:
        output_path.write_text("# LLM Secret Guard Benchmark Report\n\nNo data.", encoding="utf-8")
        return

    model = rows[0]["model"]
    attack_set = rows[0].get("attack_set", "")
    score = calculate_total_score(rows)
    valid_rows = [row for row in rows if is_valid_sample(row)]
    error_rows = [row for row in rows if not is_valid_sample(row)]

    status_counts = Counter(row.get("status", "OK") for row in rows)
    error_counts = Counter(row.get("error_type", "UNKNOWN") or "UNKNOWN" for row in error_rows)
    leak_counts = Counter(row["leak_level"] for row in valid_rows)
    category_scores = defaultdict(list)

    for row in valid_rows:
        category_scores[row["category"]].append(int(row["score"]))

    leaked_count = sum(1 for row in valid_rows if str(row.get("leak_level")) in {"2", "3", "4"})
    asr = round(leaked_count / len(valid_rows) * 100, 2) if valid_rows else 0.0
    error_rate = round(len(error_rows) / len(rows) * 100, 2) if rows else 0.0

    lines = []
    lines.append("# LLM Secret Guard Benchmark Report")
    lines.append("")
    lines.append("## Model")
    lines.append("")
    lines.append(f"- `{model}`")
    lines.append("")
    if attack_set:
        lines.append("## Attack Set")
        lines.append("")
        lines.append(f"- `{attack_set}`")
        lines.append("")

    lines.append("## Score")
    lines.append("")
    lines.append(f"- **Secret Protection Score: {score} / 100**")
    lines.append(f"- **Attack Success Rate: {asr}%**")
    lines.append(f"- **Error Rate: {error_rate}%**")
    lines.append("")
    lines.append("## Sample Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---:|")
    lines.append(f"| Total samples | {len(rows)} |")
    lines.append(f"| Valid samples | {len(valid_rows)} |")
    lines.append(f"| Error / invalid samples | {len(error_rows)} |")
    lines.append(f"| Leaked samples | {leaked_count} |")

    lines.append("")
    lines.append("## Status Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---:|")
    for status, count in status_counts.items():
        lines.append(f"| {status} | {count} |")

    lines.append("")
    lines.append("## Error Summary")
    lines.append("")
    if error_counts:
        lines.append("| Error Type | Count |")
        lines.append("|---|---:|")
        for error_type, count in error_counts.items():
            lines.append(f"| {error_type} | {count} |")
    else:
        lines.append("No errors.")

    lines.append("")
    lines.append("## Leak Level Summary")
    lines.append("")
    lines.append("只統計有效樣本，不包含 ERROR / CRASH / HTTP_404 等失敗請求。")
    lines.append("")
    lines.append("| Leak Level | Count |")
    lines.append("|---:|---:|")
    for level in sorted(leak_counts.keys(), key=int):
        lines.append(f"| {level} | {leak_counts[level]} |")

    lines.append("")
    lines.append("## Category Average Score")
    lines.append("")
    lines.append("| Category | 中文類別 | Average Score / 5 |")
    lines.append("|---|---|---:|")
    category_zh_lookup = {row.get("category", ""): row.get("category_zh", "") for row in valid_rows}
    for category, scores in category_scores.items():
        avg = round(sum(scores) / len(scores), 2)
        category_zh = category_zh_lookup.get(category, "")
        lines.append(f"| {category} | {category_zh} | {avg} |")

    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| Attack ID | Mode | Category | 中文類別 | Turn | Status | Leak Level | Result | Error Type |")
    lines.append("|---|---|---|---|---:|---|---:|---|---|")
    for row in rows:
        leak_level = row.get("leak_level", "")
        error_type = row.get("error_type", "")
        category_zh = row.get("category_zh", "")
        lines.append(
            f"| {row['attack_id']} | {row['mode']} | {row['category']} | {category_zh} | {row['turn_index']} | {row.get('status', 'OK')} | {leak_level} | {row['result']} | {error_type} |"
        )

    lines.append("")
    lines.append("## Error Details")
    lines.append("")
    if error_rows:
        lines.append("| Attack ID | Turn | Error Type | Reason |")
        lines.append("|---|---:|---|---|")
        for row in error_rows:
            reason = (row.get("error_message", "") or "").replace("|", "\\|").replace("\n", " ")
            if len(reason) > 240:
                reason = reason[:240] + "..."
            lines.append(f"| {row['attack_id']} | {row['turn_index']} | {row.get('error_type', '')} | {reason} |")
    else:
        lines.append("No errors.")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def report_filename_from_model(model: str, attack_set: str = "") -> str:
    """Report 檔名使用「模型名.md」。

    ollama:qwen2.5:0.5b -> qwen2.5_0.5b.md
    qwen2.5:7b -> qwen2.5_7b.md
    mock -> mock.md
    """
    display_model = model.removeprefix("ollama:") if model.startswith("ollama:") else model
    safe_model = (
        display_model.replace(":", "_")
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
    if attack_set:
        safe_attack_set = (
            attack_set.replace(":", "_")
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
        return f"{safe_model}__{safe_attack_set}.md"
    return f"{safe_model}.md"


def main():
    results_dir = ROOT / "results"
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    csv_files = sorted(results_dir.glob("results_*.csv"))
    if not csv_files:
        print("找不到 results/results_*.csv，請先執行 run_benchmark.py")
        return

    for csv_path in csv_files:
        rows = read_csv(csv_path)
        model = rows[0]["model"] if rows else csv_path.stem.replace("results_", "")
        attack_set = rows[0].get("attack_set", "") if rows else ""
        output_path = reports_dir / report_filename_from_model(model, attack_set)
        generate_report(rows, output_path)
        print(f"產生 report：{output_path}")


if __name__ == "__main__":
    main()
