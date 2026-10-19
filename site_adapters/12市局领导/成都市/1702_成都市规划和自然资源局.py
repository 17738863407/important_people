from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1702",
    "page_type": "人物列表完整页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".zc_ld",
    "item_selector": ".zc_ld",
    "risk_note": "领导分工块按姓名行、冒号后职务与职责行交替；主职务只保留冒号后完整首句。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def clean_evidence(value: str) -> str:
    """删除无期限独立兼任标记和纯句末句号，保留实际任职语义。"""
    value = re.sub(r"[（(]\s*兼\s*[)）]", "", value)
    value = re.sub(r"\s*。\s*$", "", value)
    return re.sub(r"\s*([、，])\s*", r"\1", value).strip(" 、，")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导分工块的姓名/说明交替顺序提取姓名和完整职务首句。"""
    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one(page_rule["leader_region_selector"])
    if block is None:
        return []
    lines = [clean_text(line) for line in block.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    rows: list[dict] = []

    for index in range(0, len(lines) - 1, 2):
        name = re.sub(r"\s+", "", lines[index])
        duty_text = re.sub(r"^[:：]\s*", "", lines[index + 1])
        first_sentence = duty_text.split("。", 1)[0].strip()
        evidence = clean_evidence(first_sentence)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": "",
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
