from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0163",
    "page_type": "多人物详情合并页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".bsfw_list",
    "item_selector": ".bsfw_list p",
    "risk_note": "HTTP采集受防护，需浏览器DOM；人物简历段含姓名和唯一完整现任句，下一段为分工。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """清除浏览器DOM中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def clean_duty_evidence(value: str) -> str:
    """删除现任句的固定引导词和纯句末句号。"""
    text = re.sub(r"^现任\s*", "", clean_text(value))
    return re.sub(r"[。．]\s*$", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按合并详情页简历段顺序提取姓名及完整现任原句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for paragraph in soup.select(page_rule["item_selector"]):
        text = clean_text(paragraph.get_text("", strip=True))
        match = re.search(
            r"(?:简历[:：])?(?P<name>[\u4e00-\u9fff·]{2,8})[，,][男女][，,].*?(?P<evidence>现任[^。]+。)",
            text,
        )
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_duty_evidence(match.group("evidence"))
        if name in seen:
            continue
        seen.add(name)
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
