from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3440",
    "page_type": "人物分组卡片页",
    "structure_group": "职务标题与后续人物容器",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "HaikouCppccGroupedLeaderCardParser_v2",
    "leader_region_selector": "div#zk_manage > div.ldy",
    "risk_flag": "同一职务分组可能跨连续多个人物容器",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按直接子容器顺序维护当前职务并展开人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(rule["leader_region_selector"])
    if container is None:
        return []
    records: list[dict] = []
    seen: set[str] = set()
    current_duty = ""
    for child in container.find_all("div", recursive=False):
        classes = child.get("class") or []
        if "ldy-lm2" in classes:
            current_duty = _clean_text(child.get_text(" ", strip=True))
            continue
        if not current_duty:
            continue
        for link in child.select("a[href]"):
            name = _clean_name(link.get("title") or link.get_text(" ", strip=True))
            href = (link.get("href") or "").strip()
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
                continue
            seen.add(name)
            records.append(
                {
                    "name": name,
                    "duty": current_duty,
                    "evidence": current_duty,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": ".ldy直接子容器中的ldy-lm2职务与后续人物链接",
                }
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
