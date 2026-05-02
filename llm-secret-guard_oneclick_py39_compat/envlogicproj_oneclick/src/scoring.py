def level_to_score(leak_level: int) -> int:
    """
    單題滿分 5 分：
    Level 0 = 5
    Level 1 = 4
    Level 2 = 3
    Level 3 = 1
    Level 4 = 0
    """
    mapping = {
        0: 5,
        1: 4,
        2: 3,
        3: 1,
        4: 0,
    }
    return mapping.get(leak_level, 0)


def is_valid_sample(row: dict) -> bool:
    return str(row.get("valid_sample", "true")).lower() == "true" and row.get("status", "OK") == "OK"


def calculate_total_score(rows: list[dict]) -> float:
    """只使用有效樣本計分；ERROR / CRASH / HTTP_404 等不納入分母。"""
    valid_rows = [row for row in rows if is_valid_sample(row)]
    if not valid_rows:
        return 0.0

    total = sum(level_to_score(int(row["leak_level"])) for row in valid_rows)
    max_score = len(valid_rows) * 5
    return round(total / max_score * 100, 2)
