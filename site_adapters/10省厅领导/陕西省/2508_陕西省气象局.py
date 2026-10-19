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
    "rule_id": "2508",
    "page_type": "人物列表完整页",
    "structure_group": "responsible_person_duty_colon_name_links",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiCmaResponsiblePersonParser_v1",
    "leader_region_selector": "a[href*='fzrjbxx']",
    "name_selector": "冒号后文本",
    "duty_selector": "冒号前文本",
    "detail_link_selector": "a[href*='fzrjbxx']",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "当前HTTP响应已静态直出负责人列表；不得保留固定人员、职务或详情链接",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按负责人链接顺序动态解析“职务：姓名”。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href*='fzrjbxx']"):
        text = _clean_text(link.get_text(" ", strip=True))
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = _clean_text(parts[0])
        name = re.sub(r"\s+", "", parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "a[href*='fzrjbxx']；职务=冒号前文本；姓名=冒号后文本；详情=当前href",
                "order": str(len(records) + 1),
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
