from __future__ import annotations

import re
import unicodedata


def parse_review_response(text: str) -> bool | None:
    """Accept an exact local reply, never a substring or a model interpretation."""
    normalized = unicodedata.normalize("NFKC", text).strip().casefold()
    normalized = re.sub(r"^스킬라[\s,.!?:]*", "", normalized).strip(" \t,.!?。")
    if normalized in {"예", "네", "응", "등록해", "등록해 줘", "등록해줘", "실행해", "실행해줘"}:
        return True
    if normalized in {"아니", "아니요", "아니오", "취소", "하지 마", "하지마"}:
        return False
    return None
