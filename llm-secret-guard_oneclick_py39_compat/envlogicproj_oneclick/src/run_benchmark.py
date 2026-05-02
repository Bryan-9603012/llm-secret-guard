from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from model_client import get_client
from leak_detector import detect_leak
from scoring import level_to_score, calculate_total_score

try:
    from clients.ollama_client import OllamaClientError
except Exception:  # pragma: no cover
    OllamaClientError = RuntimeError


ROOT = Path(__file__).resolve().parents[1]


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
            .replace('"', "_")
    )


def load_flag() -> str:
    return (ROOT / "data" / "protected_data.txt").read_text(encoding="utf-8").strip()


def load_system_prompt(flag: str) -> str:
    template = (ROOT / "prompts" / "system_prompt.txt").read_text(encoding="utf-8")
    return template.format(flag=flag)


def resolve_attacks_path(value: str) -> Path:
    """Resolve an attacks JSON path.

    Accepted examples:
    - attacks/attacks.json
    - attacks_100_balanced.json
    - /absolute/path/to/attacks_020_balanced.json
    """
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    attacks_candidate = ROOT / "attacks" / value
    if attacks_candidate.exists():
        return attacks_candidate
    return ROOT / value


def load_attacks(attacks_path: Path) -> list[dict]:
    if not attacks_path.exists():
        raise FileNotFoundError(f"找不到 attacks 檔案：{attacks_path}")
    return json.loads(attacks_path.read_text(encoding="utf-8"))


def attack_set_name(attacks_path: Path, run_name: str | None = None) -> str:
    return safe_filename(run_name or attacks_path.stem)


def classify_exception(exc: Exception) -> tuple[str, str, str]:
    """回傳 status, error_type, error_message。"""
    if isinstance(exc, OllamaClientError):
        return "ERROR", getattr(exc, "error_type", "OLLAMA_ERROR"), str(exc)

    name = exc.__class__.__name__
    msg = str(exc)
    lowered = msg.lower()

    if "connection" in lowered or "連線" in msg:
        return "ERROR", "CONNECTION_ERROR", msg
    if "404" in lowered:
        return "ERROR", "HTTP_404", msg
    if "not found" in lowered and "model" in lowered:
        return "ERROR", "MODEL_NOT_FOUND", msg

    return "CRASH", name, msg


def error_row(model_name: str, attack: dict, turn: dict, turn_index: int, exc: Exception, attack_set: str) -> dict:
    status, error_type, error_message = classify_exception(exc)
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "attack_id": attack["id"],
        "mode": attack.get("mode", "single_turn"),
        "category": attack.get("category", ""),
        "turn_index": turn_index,
        "prompt": turn.get("content", ""),
        "response": "",
        "leak_level": "",
        "score": "",
        "result": "ERROR",
        "status": status,
        "valid_sample": "false",
        "error_type": error_type,
        "error_message": error_message,
        "format_violation": "",
        "reasons": f"請求失敗，無法判斷是否洩漏。原因：{error_type}",
        "description": attack.get("description", ""),
        "category_zh": attack.get("category_zh", ""),
        "attack_set": attack_set,
    }


def success_row(model_name: str, attack: dict, turn: dict, turn_index: int, response: str, flag: str, attack_set: str) -> dict:
    leak = detect_leak(response, flag)
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "attack_id": attack["id"],
        "mode": attack.get("mode", "single_turn"),
        "category": attack.get("category", ""),
        "turn_index": turn_index,
        "prompt": turn["content"],
        "response": response,
        "leak_level": leak.leak_level,
        "score": level_to_score(leak.leak_level),
        "result": leak.result,
        "status": "OK",
        "valid_sample": "true",
        "error_type": "",
        "error_message": "",
        "format_violation": leak.format_violation,
        "reasons": " | ".join(leak.reasons),
        "description": attack.get("description", ""),
        "category_zh": attack.get("category_zh", ""),
        "attack_set": attack_set,
    }


def run_attack(client, model_name: str, system_prompt: str, flag: str, attack: dict, temperature: float, max_tokens: int, attack_set: str) -> list[dict]:
    """
    單輪：每題獨立 session。
    多輪：只在同一題內保留上下文，且固定依照 attacks.json 的 turns 執行。

    若某一輪發生 API / HTTP / 崩潰錯誤，會寫入 ERROR row，不會被算成 NO_LEAK。
    """
    rows = []
    messages = [{"role": "system", "content": system_prompt}]

    for turn_index, turn in enumerate(attack["turns"], start=1):
        messages.append(turn)

        try:
            response = client.generate(messages, temperature=temperature, max_tokens=max_tokens)
            messages.append({"role": "assistant", "content": response})
            rows.append(success_row(model_name, attack, turn, turn_index, response, flag, attack_set))
        except Exception as exc:
            rows.append(error_row(model_name, attack, turn, turn_index, exc, attack_set))
            # 多輪攻擊若中途錯誤，後續上下文已不可信，停止該 attack。
            break

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="mock", help="mock / ollama:<model_name>")
    parser.add_argument("--ollama-url", default=None, help="Ollama API URL，例如 http://127.0.0.1:11434")
    parser.add_argument("--temperature", type=float, default=0)
    parser.add_argument("--max-tokens", type=int, default=300)
    parser.add_argument(
        "--attacks",
        default="attacks/attacks.json",
        help="攻擊資料集 JSON，例如 attacks/attacks_100_balanced.json",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="自訂本次輸出名稱；預設使用 attacks 檔名。",
    )
    args = parser.parse_args()

    flag = load_flag()
    system_prompt = load_system_prompt(flag)
    attacks_path = resolve_attacks_path(args.attacks)
    attack_set = attack_set_name(attacks_path, args.run_name)
    attacks = load_attacks(attacks_path)
    client = get_client(args.model, ollama_url=args.ollama_url)

    print("=== Benchmark Config ===")
    print(f"Project root : {ROOT}")
    print(f"Model        : {args.model}")
    print(f"Ollama URL   : {args.ollama_url or 'default / env OLLAMA_URL'}")
    print(f"Attacks file : {attacks_path}")
    print(f"Attack set   : {attack_set}")
    print(f"Attack cases : {len(attacks)}")
    print("Timeout      : disabled")
    print("========================")

    all_rows = []

    for index, attack in enumerate(attacks, start=1):
        print(f"[{index}/{len(attacks)}] running {attack['id']} - {attack.get('category', '')}")
        rows = run_attack(
            client=client,
            model_name=args.model,
            system_prompt=system_prompt,
            flag=flag,
            attack=attack,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            attack_set=attack_set,
        )
        all_rows.extend(rows)

    output_path = ROOT / "results" / f"results_{safe_filename(args.model)}__{attack_set}.csv"
    output_path.parent.mkdir(exist_ok=True)

    if not all_rows:
        print("沒有任何測試結果。")
        return

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    valid_count = sum(1 for row in all_rows if row.get("valid_sample") == "true")
    error_count = len(all_rows) - valid_count
    leaked_count = sum(1 for row in all_rows if row.get("status") == "OK" and str(row.get("leak_level")) in {"2", "3", "4"})
    total_score = calculate_total_score(all_rows)

    print("\n測試結束")
    print(f"結果檔案：{output_path}")
    print(f"總樣本數：{len(all_rows)}")
    print(f"有效樣本：{valid_count}")
    print(f"錯誤樣本：{error_count}")
    print(f"洩漏樣本：{leaked_count}")
    print(f"Secret Protection Score: {total_score}")


if __name__ == "__main__":
    main()
