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
    "rule_id": "3483",
    "page_type": "人物列表完整页",
    "structure_group": "中国商飞领导人物卡片标题字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ComacLeaderTitleParser_v2",
    "leader_region_selector": ".nr ul.leaders1 li, .nr ul.leaders2 li",
    "name_selector": "a[title]首个姓名字段",
    "duty_selector": "a[title]姓名后完整职务字段",
    "detail_link_selector": "a[title][href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "领导分布于leaders1和leaders2两个连续列表；必须全部覆盖并保持DOM顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _parse_title(value: str) -> tuple[str, str]:
    text = _clean_text(value)
    matched = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})\s+(.+)", text)
    return matched.groups() if matched else ("", "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按两个领导列表的联合DOM顺序解析姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".nr ul.leaders1 li, .nr ul.leaders2 li"):
        link = card.select_one("a[title][href]")
        if link is None:
            continue
        name, evidence = _parse_title(str(link.get("title", "")))
        if not name or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, str(link.get("href", ""))),
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".nr ul.leaders1/2 li；a title拆姓名职务；href人物详情",
            }
        )
    if not records:
        raise RuntimeError("中国商飞领导列表未解析到人物记录")
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
