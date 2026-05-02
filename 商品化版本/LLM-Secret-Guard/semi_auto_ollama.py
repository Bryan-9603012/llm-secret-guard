"""
兩終端機半自動 Ollama 測試流程。

設計原則：
- Terminal A：使用者手動啟動 Ollama，例如 `ollama serve`。
- Terminal B：執行本腳本，負責選模型、必要時 pull 模型、跑 benchmark、產生 report。
- 預設使用類似 opencode 的方向鍵選單；不支援時自動退回數字選單。
- 所有手動輸入畫面統一使用 Esc 返回上一層。
- 不使用滑鼠點選或 prompt_toolkit 全螢幕介面，避免學校電腦 / CMD 環境不穩。
- 產品化原型：提供設定檔、環境檢查、模型清單管理、單模型/批次測試、執行摘要。
- 不設定 request timeout，因為本地模型回應時間差異很大。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from collections import Counter
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
MODEL_LIST_PATH = ROOT / "model_list.txt"
RUN_STATE = {"session_id": "", "started_at": "", "rows": []}
APP_CONFIG: dict = {}
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("MODEL", "qwen2.5:0.5b")
DEFAULT_ATTACK_SET = "attacks/attacks_100_balanced.json"
DEFAULT_RUN_COUNT = 1
AUTO_PULL_MISSING = False
SIMPLE_MODE = False


class BackToMenu(Exception):
    """Raised when a submenu requests returning to the previous menu."""


@dataclass
class SelectOption:
    label: str
    value: str
    hint: str = ""



def load_config() -> dict:
    """Load product settings from config.json, creating a sane default when missing."""
    default = {
        "app_name": "LLM Secret Guard",
        "ollama_url": "http://127.0.0.1:11434",
        "default_model": "qwen2.5:0.5b",
        "default_attack_set": "attacks/attacks_100_balanced.json",
        "default_run_count": 1,
        "auto_pull_missing_models": False,
        "max_run_count": 50,
        "output": {
            "results_dir": "results",
            "reports_dir": "reports",
            "logs_dir": "logs"
        },
        "ui": {
            "default_simple_mode": False,
            "esc_returns": True
        }
    }
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return default

    try:
        user_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] CONFIG_INVALID：config.json 無法讀取，改用預設設定。原因：{exc}")
        return default

    def merge(base: dict, override: dict) -> dict:
        merged = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    return merge(default, user_cfg)


def apply_config(config: dict) -> None:
    global APP_CONFIG, OLLAMA_URL, DEFAULT_MODEL, DEFAULT_ATTACK_SET, DEFAULT_RUN_COUNT, AUTO_PULL_MISSING, SIMPLE_MODE
    APP_CONFIG = config
    OLLAMA_URL = os.getenv("OLLAMA_URL", str(config.get("ollama_url", OLLAMA_URL))).rstrip("/")
    DEFAULT_MODEL = os.getenv("MODEL", str(config.get("default_model", DEFAULT_MODEL)))
    DEFAULT_ATTACK_SET = str(config.get("default_attack_set", DEFAULT_ATTACK_SET))
    try:
        DEFAULT_RUN_COUNT = max(1, int(config.get("default_run_count", 1)))
    except Exception:
        DEFAULT_RUN_COUNT = 1
    AUTO_PULL_MISSING = bool(config.get("auto_pull_missing_models", False))
    SIMPLE_MODE = bool(config.get("ui", {}).get("default_simple_mode", False))


def ensure_product_dirs() -> None:
    for rel in ["results", "reports", "logs", "reports/figures"]:
        (ROOT / rel).mkdir(parents=True, exist_ok=True)


def start_run_session() -> None:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    RUN_STATE["session_id"] = now
    RUN_STATE["started_at"] = datetime.now().isoformat(timespec="seconds")
    RUN_STATE["rows"] = []


def record_run_result(model: str, attack_set: str, ok: bool, report_path: Path | None = None, result_path: Path | None = None) -> None:
    RUN_STATE["rows"].append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "attack_set": attack_set,
        "status": "OK" if ok else "FAILED_OR_SKIPPED",
        "report": str(report_path.relative_to(ROOT)) if report_path and report_path.exists() else "",
        "result": str(result_path.relative_to(ROOT)) if result_path and result_path.exists() else "",
    })


def write_session_summary() -> None:
    rows = RUN_STATE.get("rows") or []
    if not rows:
        return
    logs_dir = ROOT / "logs"
    reports_dir = ROOT / "reports"
    logs_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    session_id = RUN_STATE.get("session_id") or datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = logs_dir / f"session_{session_id}.csv"
    md_path = reports_dir / f"session_summary_{session_id}.md"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "model", "attack_set", "status", "report", "result"])
        writer.writeheader()
        writer.writerows(rows)

    ok_count = sum(1 for row in rows if row["status"] == "OK")
    lines = [
        "# LLM Secret Guard Session Summary",
        "",
        f"- Session ID: `{session_id}`",
        f"- Started at: `{RUN_STATE.get('started_at', '')}`",
        f"- Total model runs: {len(rows)}",
        f"- Successful model runs: {ok_count}",
        f"- Failed / skipped model runs: {len(rows) - ok_count}",
        "",
        "| Model | Attack Set | Status | Report | Result |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['model']}` | `{row['attack_set']}` | {row['status']} | {row['report']} | {row['result']} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[OK] Session summary：{md_path}")
    print(f"[OK] Session CSV：{csv_path}")


def product_preflight() -> bool:
    """Local environment checks before entering the interactive flow."""
    ensure_product_dirs()
    print("\n[0/5] 環境檢查")
    ok = True
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[OK] Python：{py_version}")
    if sys.version_info < (3, 9):
        print("[ERROR] Python 版本過舊，建議使用 Python 3.9+。")
        ok = False

    ollama_bin = shutil.which("ollama")
    if ollama_bin:
        print(f"[OK] Ollama command：{ollama_bin}")
    else:
        print("[WARN] 找不到 ollama 指令；若只用 API 測試，仍可繼續，但無法自動 pull 模型。")

    if MODEL_LIST_PATH.exists():
        print(f"[OK] 模型清單：{MODEL_LIST_PATH.name}")
    else:
        MODEL_LIST_PATH.write_text(DEFAULT_MODEL + "\n", encoding="utf-8")
        print(f"[OK] 已建立模型清單：{MODEL_LIST_PATH.name}")

    default_attack = ROOT / DEFAULT_ATTACK_SET
    if default_attack.exists():
        print(f"[OK] 預設攻擊資料集：{DEFAULT_ATTACK_SET}")
    else:
        fallback = list_attack_files()
        if fallback:
            print(f"[WARN] 預設攻擊資料集不存在，稍後會改由選單選擇：{DEFAULT_ATTACK_SET}")
        else:
            print("[ERROR] 找不到 attacks/*.json，無法執行 benchmark。")
            ok = False
    return ok


def supports_tui() -> bool:
    if SIMPLE_MODE:
        return False
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        return True
    return bool(os.getenv("TERM")) and os.getenv("TERM") != "dumb"


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


def read_key() -> str:
    """Read one navigation key without requiring Enter. Supports Windows and Unix-like terminals."""
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(ch2, "")
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x1b":
            return "ESC"
        return ch.lower()

    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "UP"
            if seq == "[B":
                return "DOWN"
            if seq == "[D":
                return "LEFT"
            if seq == "[C":
                return "RIGHT"
            return "ESC"
        if ch in ("\r", "\n"):
            return "ENTER"
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def numeric_select(title: str, options: list[SelectOption], default_index: int = 0) -> SelectOption:
    print(f"\n{title}")
    for idx, option in enumerate(options, start=1):
        suffix = f"  {option.hint}" if option.hint else ""
        print(f"  {idx}. {option.label}{suffix}")
    value_raw = esc_input(f"請輸入數字 [{default_index + 1}]：")
    if value_raw is None:
        return SelectOption("取消", "__cancel__")
    value = value_raw.strip()
    if not value:
        return options[default_index]
    try:
        choice = int(value)
        if 1 <= choice <= len(options):
            return options[choice - 1]
    except ValueError:
        pass
    print("[WARN] 選項無效，改用預設值。")
    return options[default_index]


def tui_select(title: str, options: list[SelectOption], default_index: int = 0) -> SelectOption:
    """opencode-like direction-key selector; falls back to numeric selector."""
    if not options:
        raise ValueError("tui_select requires at least one option")
    if not supports_tui():
        return numeric_select(title, options, default_index)

    index = max(0, min(default_index, len(options) - 1))
    while True:
        clear_screen()
        print(title)
        print("─" * 48)
        for idx, option in enumerate(options):
            pointer = "❯" if idx == index else " "
            suffix = f"  {option.hint}" if option.hint else ""
            print(f"{pointer} {option.label}{suffix}")

        try:
            key = read_key()
        except Exception as exc:
            clear_screen()
            print(f"[WARN] 互動選單失敗，已切換成數字選單：{exc}")
            return numeric_select(title, options, default_index)

        if key in {"UP", "k"}:
            index = (index - 1) % len(options)
        elif key in {"DOWN", "j"}:
            index = (index + 1) % len(options)
        elif key == "ENTER":
            clear_screen()
            return options[index]
        elif key == "ESC":
            clear_screen()
            return SelectOption("取消", "__cancel__")
        elif key.isdigit():
            n = int(key)
            if 1 <= n <= len(options):
                index = n - 1


def tui_confirm(
    question: str,
    default: bool = True,
    yes_label: str = "是 / Yes",
    no_label: str = "否 / No",
) -> bool:
    option = tui_select(
        question,
        [SelectOption(yes_label, "yes"), SelectOption(no_label, "no")],
        0 if default else 1,
    )
    # Esc 統一視為取消，不執行具有副作用的動作。
    if option.value == "__cancel__":
        return False
    return option.value == "yes"




def esc_input(prompt: str, default: Optional[str] = None) -> Optional[str]:
    """Read a line while allowing ESC to return to the previous menu.

    Returns:
        - None when user presses ESC
        - default when user presses Enter on an empty input and default is not None
        - typed string otherwise
    """
    if default is not None and "[" not in prompt:
        prompt = f"{prompt} [{default}]"
    if not prompt.endswith(" "):
        prompt += " "

    # Fallback for redirected/non-interactive input.
    if not sys.stdin.isatty():
        value = input(prompt).strip()
        return default if value == "" and default is not None else value

    print(prompt, end="", flush=True)
    chars: list[str] = []

    if os.name == "nt":
        import msvcrt

        while True:
            ch = msvcrt.getwch()
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x1b":
                print("\n[返回]", flush=True)
                return None
            if ch in ("\r", "\n"):
                print()
                value = "".join(chars).strip()
                return default if value == "" and default is not None else value
            if ch in ("\b", "\x7f"):
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue
            if ch in ("\x00", "\xe0"):
                # Consume special key suffix and ignore it.
                _ = msvcrt.getwch()
                continue
            if ch.isprintable():
                chars.append(ch)
                print(ch, end="", flush=True)
        
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x1b":
                print("\n[返回]", flush=True)
                return None
            if ch in ("\r", "\n"):
                print()
                value = "".join(chars).strip()
                return default if value == "" and default is not None else value
            if ch in ("\b", "\x7f"):
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue
            if ch.isprintable():
                chars.append(ch)
                print(ch, end="", flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def wait_enter_or_esc(prompt: str = "按 Esc 返回...") -> None:
    """Compatibility wrapper: wait until user presses Esc/Enter.

    The UI text now standardizes on Esc for returning. Enter is still accepted
    as a harmless fallback for terminals that cannot send Esc cleanly.
    """
    if supports_tui():
        print(prompt, end="", flush=True)
        while True:
            try:
                key = read_key()
            except Exception:
                _ = esc_input(prompt)
                return
            if key in {"ESC", "ENTER"}:
                print()
                return
    else:
        _ = esc_input(prompt)



def read_model_list() -> list[str]:
    if not MODEL_LIST_PATH.exists():
        return []
    models: list[str] = []
    for line in MODEL_LIST_PATH.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if name not in models:
            models.append(name)
    return models


def write_model_list(models: list[str]) -> None:
    unique: list[str] = []
    for model in models:
        model = model.strip()
        if model and model not in unique:
            unique.append(model)
    MODEL_LIST_PATH.write_text("\n".join(unique) + ("\n" if unique else ""), encoding="utf-8")


def add_model_to_list(model: str) -> None:
    model = model.strip()
    if not model:
        return
    models = read_model_list()
    if model in models:
        print(f"[OK] 模型已在清單中：{model}")
        return
    models.append(model)
    write_model_list(models)
    print(f"[OK] 已加入模型清單：{model}")


def remove_model_from_list(model: str) -> None:
    models = read_model_list()
    if model not in models:
        print(f"[WARN] 模型不在清單中：{model}")
        return
    write_model_list([m for m in models if m != model])
    print(f"[OK] 已從模型清單移除：{model}")


def model_status(model: str, installed_models: list[str]) -> str:
    return "已下載" if model in installed_models else "未下載"


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


def report_filename_from_model(model: str, attack_set: str = "") -> str:
    suffix = f"__{safe_filename(attack_set)}" if attack_set else ""
    return f"{safe_filename(model)}{suffix}.md"


def list_attack_files() -> list[Path]:
    attacks_dir = ROOT / "attacks"
    files = sorted(attacks_dir.glob("*.json"))
    preferred = [
        attacks_dir / "attacks_100_balanced.json",
        attacks_dir / "attacks_020_balanced.json",
        attacks_dir / "attacks.json",
    ]
    ordered: list[Path] = []
    for path in preferred + files:
        if path.exists() and path not in ordered:
            ordered.append(path)
    return ordered


def ask_attacks_file() -> Path:
    files = list_attack_files()
    if not files:
        default_path = ROOT / "attacks" / "attacks.json"
        print(f"[WARN] 找不到 attacks/*.json，改用預設：{default_path}")
        return default_path

    options: list[SelectOption] = []
    default_path = ROOT / DEFAULT_ATTACK_SET
    default_index = 0
    for path in files:
        rel = str(path.relative_to(ROOT))
        marker = "[預設]" if path == default_path else ("[推薦]" if path.name == "attacks_100_balanced.json" else "")
        if path == default_path:
            default_index = len(options)
        options.append(SelectOption(rel, str(path), marker))
    options.append(SelectOption("手動輸入 attacks 檔案路徑", "__manual__"))
    options.append(SelectOption("返回", "back"))

    selected = tui_select("選擇攻擊資料集", options, default_index=default_index)
    if selected.value == "__manual__":
        value = esc_input("請輸入 attacks 檔案路徑，Esc 返回：")
        if value is None:
            raise BackToMenu
        value = value.strip()
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = ROOT / value
        return candidate
    if selected.value in {"back", "__cancel__"}:
        raise BackToMenu
    return Path(selected.value)


def ask_run_count() -> int:
    max_run_count = int(APP_CONFIG.get("max_run_count", 50) or 50)
    value = esc_input(f"請輸入本次執行次數 [{DEFAULT_RUN_COUNT}]，Esc 返回：")
    if value is None:
        raise BackToMenu
    value = value.strip()
    if not value:
        return DEFAULT_RUN_COUNT
    try:
        count = int(value)
        if count < 1:
            print("[WARN] 執行次數不可小於 1，改用 1。")
            return 1
        if count > max_run_count:
            print(f"[WARN] 執行次數過大，本次上限設為 {max_run_count}。")
            return max_run_count
        return count
    except ValueError:
        print(f"[WARN] 執行次數格式錯誤，改用 {DEFAULT_RUN_COUNT}。")
        return DEFAULT_RUN_COUNT


def explain_request_error(exc: Exception) -> str:
    msg = str(exc)
    lowered = msg.lower()
    if "connection refused" in lowered or "failed to establish" in lowered:
        return (
            "OLLAMA_UNREACHABLE：無法連線到 Ollama。"
            "請先在另一個終端機執行 `ollama serve`，再重新跑本腳本。"
            f" 原始錯誤：{msg}"
        )
    if "404" in lowered:
        return f"HTTP_404：Ollama API 路徑或 URL 可能錯誤。原始錯誤：{msg}"
    return f"REQUEST_ERROR：{msg}"


def print_two_terminal_help() -> None:
    print("=== LLM Secret Guard ===")
    print("模式：產品化原型 / 本地 Ollama 安全測試流程")
    print("")
    print("Terminal A：先啟動 Ollama")
    print("  ollama serve")
    print("")
    print("Terminal B：再執行本腳本")
    print("  python llm_secret_guard.py")
    print("")
    print(f"Project root：{ROOT}")
    print(f"Config：{CONFIG_PATH.name}")
    print(f"Ollama URL：{OLLAMA_URL}")
    print(f"Default model：{DEFAULT_MODEL}")
    print(f"Default attack set：{DEFAULT_ATTACK_SET}")
    print(f"Default run count：{DEFAULT_RUN_COUNT}")
    print("Timeout：disabled")


def check_ollama() -> Optional[list[str]]:
    url = f"{OLLAMA_URL}/api/tags"
    print(f"\n[1/5] 檢查 Ollama API：{url}")
    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as exc:
        print("[ERROR]", explain_request_error(exc))
        return None

    if response.status_code == 404:
        print(f"[ERROR] HTTP_404：找不到 {url}。請確認 OLLAMA_URL 是否正確。")
        return None
    if response.status_code != 200:
        print(f"[ERROR] HTTP_{response.status_code}：{response.text.strip()}")
        return None

    try:
        data = response.json()
    except ValueError:
        print(f"[ERROR] INVALID_JSON：Ollama /api/tags 回應不是 JSON：{response.text[:300]}")
        return None

    models = [item.get("name", "") for item in data.get("models", []) if item.get("name")]
    print(f"[OK] Ollama 已連線，目前已下載模型數：{len(models)}")
    return models


def build_model_options(installed_models: list[str], include_actions: bool = True) -> list[SelectOption]:
    saved_models = read_model_list()
    combined: list[str] = []
    for name in installed_models + saved_models:
        if name and name not in combined:
            combined.append(name)
    if DEFAULT_MODEL not in combined:
        combined.append(DEFAULT_MODEL)

    options = [SelectOption(f"{name} : {model_status(name, installed_models)}", name) for name in combined]
    if include_actions:
        options.extend([
            SelectOption("管理模型清單", "__manage__"),
            SelectOption("手動輸入模型名稱", "__manual__"),
            SelectOption("返回", "__cancel__"),
        ])
    return options


def ask_run_mode() -> str:
    selected = tui_select(
        "選擇執行模式",
        [
            SelectOption("測試單一模型", "single"),
            SelectOption("測試模型清單", "batch"),
            SelectOption("管理模型清單", "manage"),
            SelectOption("離開", "__cancel__"),
        ],
        default_index=0,
    )
    return selected.value


def download_model(model: str) -> bool:
    model = model.strip()
    if not model:
        print("[WARN] 模型名稱不可為空。")
        return False
    print(f"[RUN] ollama pull {model}")
    try:
        result = subprocess.run(["ollama", "pull", model], cwd=ROOT)
    except FileNotFoundError:
        print("[ERROR] OLLAMA_COMMAND_NOT_FOUND：系統找不到 `ollama` 指令。")
        return False
    except Exception as exc:
        print(f"[ERROR] PULL_CRASH：執行 ollama pull 時崩潰：{exc}")
        return False
    if result.returncode != 0:
        print(f"[ERROR] PULL_FAILED：ollama pull 結束碼 {result.returncode}")
        return False
    print(f"[OK] 模型下載完成：{model}")
    return True


def print_model_list_status(title: str, installed_models: list[str]) -> list[str]:
    saved_models = read_model_list()
    clean_title = title.strip().rstrip("：:")
    print(f"\n{clean_title}")
    print("─" * 48)
    print()
    if saved_models:
        for model in saved_models:
            print(f"{model} : {model_status(model, installed_models)}")
    else:
        print("[空清單]")
    print()
    return saved_models


def manage_model_list(installed_models: list[str]) -> None:
    while True:
        print_model_list_status("模型清單", installed_models)

        selected = tui_select(
            "管理模型清單",
            [
                SelectOption("查看模型清單", "view"),
                SelectOption("新增模型到清單", "add_only"),
                SelectOption("新增並下載模型", "add_pull"),
                SelectOption("從清單移除模型", "remove"),
                SelectOption("返回", "back"),
            ],
            default_index=0,
        )

        if selected.value in {"back", "__cancel__"}:
            return

        if selected.value == "view":
            print_model_list_status("模型清單", installed_models)
            wait_enter_or_esc("按 Esc 返回模型清單管理...")

        elif selected.value == "add_only":
            value = esc_input("請輸入要加入清單的模型名稱，例如 qwen2.5:0.5b，Esc 返回：")
            if value is None:
                continue
            value = value.strip()
            if value:
                add_model_to_list(value)
            wait_enter_or_esc("按 Esc 返回模型清單管理...")

        elif selected.value == "add_pull":
            value = esc_input("請輸入要新增並下載的模型名稱，例如 qwen2.5:0.5b，Esc 返回：")
            if value is None:
                continue
            value = value.strip()
            if not value:
                continue
            add_model_to_list(value)
            if download_model(value):
                refreshed = check_ollama()
                if refreshed is not None:
                    installed_models[:] = refreshed
            wait_enter_or_esc("按 Esc 返回模型清單管理...")

        elif selected.value == "remove":
            saved_models = read_model_list()
            if not saved_models:
                print("[WARN] 清單是空的，沒有模型可移除。")
                wait_enter_or_esc("按 Esc 返回模型清單管理...")
                continue
            remove_options = [SelectOption(f"{m} : {model_status(m, installed_models)}", m) for m in saved_models]
            remove_options.append(SelectOption("返回", "back"))
            target = tui_select("選擇要從清單移除的模型", remove_options, default_index=0)
            if target.value not in {"back", "__cancel__"}:
                remove_model_from_list(target.value)
            wait_enter_or_esc("按 Esc 返回模型清單管理...")

def ask_single_model(installed_models: list[str]) -> str:
    while True:
        options = build_model_options(installed_models, include_actions=True)
        default_index = 0
        for i, option in enumerate(options):
            if option.value == DEFAULT_MODEL:
                default_index = i
                break

        selected = tui_select("選擇 Ollama 模型", options, default_index=default_index)

        if selected.value == "__cancel__":
            raise BackToMenu

        if selected.value == "__manage__":
            manage_model_list(installed_models)
            continue

        if selected.value == "__manual__":
            value = esc_input(f"請輸入模型名稱 [{DEFAULT_MODEL}]，Esc 返回：", default=DEFAULT_MODEL)
            if value is None:
                continue
            value = value.strip() or DEFAULT_MODEL
            if tui_confirm(f"是否把 {value} 加入模型清單？", default=True):
                add_model_to_list(value)
            return value

        return selected.value


def get_batch_models(installed_models: list[str]) -> list[str]:
    while True:
        saved_models = print_model_list_status("模型清單", installed_models)
        selected = tui_select(
            "測試模型清單",
            [
                SelectOption("開始測試清單", "start"),
                SelectOption("下載缺少的模型後測試", "pull_then_start"),
                SelectOption("管理模型清單", "manage"),
                SelectOption("返回", "back"),
            ],
            default_index=0,
        )

        if selected.value in {"back", "__cancel__"}:
            raise BackToMenu

        if selected.value == "manage":
            manage_model_list(installed_models)
            continue

        if not saved_models:
            print("[WARN] 模型清單目前是空的，請先到「管理模型清單」新增模型。")
            wait_enter_or_esc("按 Esc 返回...")
            continue

        if selected.value == "pull_then_start":
            missing = [m for m in saved_models if m not in installed_models]
            if not missing:
                print("[OK] 清單中的模型都已下載。")
            for model in missing:
                if download_model(model):
                    refreshed = check_ollama()
                    if refreshed is not None:
                        installed_models[:] = refreshed
                else:
                    print(f"[WARN] 模型下載失敗，稍後測試時會略過或再次詢問：{model}")
            return read_model_list()

        if selected.value == "start":
            return saved_models

def ensure_model(model: str, installed_models: list[str]) -> bool:
    print("\n[3/5] 檢查模型")
    if model in installed_models:
        print(f"[OK] 模型已下載：{model}")
        return True

    print(f"[WARN] 尚未下載模型：{model}")
    if AUTO_PULL_MISSING:
        print("[INFO] config.json 已啟用 auto_pull_missing_models，將自動下載缺少模型。")
    elif not tui_confirm(
        f"模型尚未下載，是否立即下載？\n{model}",
        default=False,
        yes_label="是，立即下載",
        no_label="否，返回",
    ):
        print(f"[SKIP] 略過未下載模型：{model}")
        return False

    if not download_model(model):
        return False

    refreshed_models = check_ollama() or []
    installed_models[:] = refreshed_models
    if model not in refreshed_models:
        print(f"[ERROR] MODEL_NOT_FOUND_AFTER_PULL：pull 後仍未找到模型：{model}")
        return False
    add_model_to_list(model)
    return True


def run_command(title: str, command: list[str]) -> bool:
    print(f"\n{title}")
    print("[RUN]", " ".join(command))
    try:
        result = subprocess.run(command, cwd=ROOT)
    except Exception as exc:
        print(f"[ERROR] PROCESS_CRASH：程式執行崩潰：{exc}")
        return False
    if result.returncode != 0:
        print(f"[ERROR] PROCESS_FAILED：結束碼 {result.returncode}")
        return False
    return True


def read_results(model: str, attack_set: str) -> list[dict]:
    path = ROOT / "results" / f"results_{safe_filename('ollama:' + model)}__{safe_filename(attack_set)}.csv"
    if not path.exists():
        print(f"[ERROR] RESULT_NOT_FOUND：找不到結果檔案：{path}")
        return []
    with path.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def summarize(model: str, rows: list[dict], attack_set: str) -> None:
    print("\n[5/5] 測試結果摘要")
    if not rows:
        print("測試結束，但沒有可讀取的結果。")
        return

    valid_rows = [row for row in rows if row.get("valid_sample") == "true" and row.get("status") == "OK"]
    error_rows = [row for row in rows if row not in valid_rows]
    leaked_rows = [row for row in valid_rows if str(row.get("leak_level")) in {"2", "3", "4"}]
    error_counts = Counter(row.get("error_type") or "UNKNOWN" for row in error_rows)

    score = 0.0
    if valid_rows:
        score_sum = sum(int(row.get("score") or 0) for row in valid_rows)
        score = round(score_sum / (len(valid_rows) * 5) * 100, 2)

    asr = round(len(leaked_rows) / len(valid_rows) * 100, 2) if valid_rows else 0.0
    error_rate = round(len(error_rows) / len(rows) * 100, 2) if rows else 0.0

    report_path = ROOT / "reports" / report_filename_from_model(model, attack_set)
    result_path = ROOT / "results" / f"results_{safe_filename('ollama:' + model)}__{safe_filename(attack_set)}.csv"

    print("測試結束")
    print(f"模型：{model}")
    print(f"總樣本數：{len(rows)}")
    print(f"有效樣本：{len(valid_rows)}")
    print(f"錯誤樣本：{len(error_rows)}")
    print(f"洩漏樣本：{len(leaked_rows)}")
    print(f"Attack Success Rate：{asr}%")
    print(f"Error Rate：{error_rate}%")
    print(f"Secret Protection Score：{score} / 100")

    if error_counts:
        print("\n錯誤原因：")
        for error_type, count in error_counts.items():
            print(f"  - {error_type}: {count}")

    print(f"\nResult：{result_path}")
    print(f"Report：{report_path}")


def run_benchmark_for_model(model: str, attacks_path: Path, run_count: int, installed_models: list[str]) -> bool:
    if not ensure_model(model, installed_models):
        return False

    attack_set_base = attacks_path.stem
    model_arg = f"ollama:{model}"
    failed_runs = 0

    for run_index in range(1, run_count + 1):
        if run_count == 1:
            run_name = attack_set_base
            run_label = "1/1"
        else:
            run_name = f"{attack_set_base}__run{run_index:02d}"
            run_label = f"{run_index}/{run_count}"

        print("\n" + "=" * 40)
        print(f"執行次數：{run_label}")
        print(f"模型：{model}")
        print(f"Attack set：{attack_set_base}")
        print(f"Run name：{run_name}")
        print("=" * 40)

        benchmark_ok = run_command(
            "\n[4/5] 執行 benchmark",
            [
                sys.executable,
                "src/run_benchmark.py",
                "--model",
                model_arg,
                "--ollama-url",
                OLLAMA_URL,
                "--attacks",
                str(attacks_path),
                "--run-name",
                run_name,
            ],
        )

        report_ok = run_command(
            "\n[4.5/5] 產生 report",
            [sys.executable, "src/report_generator.py"],
        )

        rows = read_results(model, run_name)
        summarize(model, rows, run_name)
        record_run_result(
            model,
            run_name,
            benchmark_ok and report_ok and bool(rows),
            ROOT / "reports" / report_filename_from_model(model, run_name),
            ROOT / "results" / f"results_{safe_filename('ollama:' + model)}__{safe_filename(run_name)}.csv",
        )

        run_command(
            "\n[4.8/5] 更新統計圖表",
            [sys.executable, "src/plot_benchmark.py"],
        )

        if not benchmark_ok or not report_ok:
            failed_runs += 1
            print("\n[WARN] 此次執行有流程失敗，請查看上方錯誤原因與 report 的 Error Summary。")

    return failed_runs == 0


def run_one_round(installed_models: list[str]) -> int:
    """Run one interactive round. Submenu `返回` returns to the main mode menu."""
    while True:
        mode = ask_run_mode()
        if mode == "__cancel__":
            return 1

        try:
            if mode == "single":
                models = [ask_single_model(installed_models)]
            elif mode == "batch":
                models = get_batch_models(installed_models)
            elif mode == "manage":
                manage_model_list(installed_models)
                continue
            else:
                return 1

            attacks_path = ask_attacks_file()
            run_count = ask_run_count()

        except BackToMenu:
            continue
        except KeyboardInterrupt:
            return 1

        failed_models: list[str] = []
        for idx, model in enumerate(models, start=1):
            print("\n" + "#" * 50)
            print(f"模型進度：{idx}/{len(models)}")
            print(f"目前模型：{model}")
            print("#" * 50)
            ok = run_benchmark_for_model(model, attacks_path, run_count, installed_models)
            if not ok:
                failed_models.append(model)

        if len(models) > 1:
            print("\n" + "=" * 40)
            print("清單批次執行摘要")
            print(f"總模型數：{len(models)}")
            print(f"成功模型數：{len(models) - len(failed_models)}")
            print(f"失敗 / 略過模型數：{len(failed_models)}")
            if failed_models:
                for model in failed_models:
                    print(f"  - {model}")
            print("=" * 40)

        return 1 if failed_models else 0


def ask_continue() -> bool:
    print("\n" + "-" * 40)
    return tui_confirm("是否繼續測下一回合？", default=False)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semi-auto Ollama benchmark runner")
    parser.add_argument(
        "--simple",
        action="store_true",
        help="強制使用數字選單；如果方向鍵互動選單異常，可以使用這個模式。",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="只做環境檢查，不進入測試流程。",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="等同 --preflight-only；給一般使用者做快速環境診斷。",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    global SIMPLE_MODE
    args = parse_args(sys.argv[1:] if argv is None else argv)
    apply_config(load_config())
    SIMPLE_MODE = bool(args.simple) or SIMPLE_MODE
    start_run_session()

    exit_code = 0
    try:
        print_two_terminal_help()
        if not product_preflight():
            print("\n[ERROR] 環境檢查未通過，請先修正上方問題。")
            return 1
        if args.preflight_only or args.doctor:
            print("\n[OK] 環境檢查完成。")
            return 0

        last_code = 0
        round_no = 1

        while True:
            print(f"\n===== 測試回合 #{round_no} =====")

            installed_models = check_ollama()
            if installed_models is None:
                print("\n測試結束：Ollama 連線失敗，未執行 benchmark。")
                print("如果你是單獨執行本腳本，請先執行 `ollama serve`。")
                return 1

            last_code = run_one_round(installed_models)

            if not ask_continue():
                print("\n已結束測試流程。")
                return last_code

            round_no += 1
    except KeyboardInterrupt:
        print("\n[INFO] 使用者中斷。")
        exit_code = 1
        return exit_code
    finally:
        write_session_summary()


if __name__ == "__main__":
    raise SystemExit(main())
