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
    "rule_id": "1096",
    "page_type": "人物列表完整页",
    "structure_group": "海岛研究中心姓名职务链接项",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "IrcMnrCurrentLeaderListParser_v2",
    "leader_region_selector": ".div1",
    "name_selector": ".div1文本开头",
    "duty_selector": ".div1姓名后文本",
    "detail_link_selector": ".div1的父级a[href]",
    "detail_strategy": {"required": False, "mode": "parent_link"},
    "risk_flag": "每条列表项外层链接为独立人物页；不得在缺失链接时以入口页兜底",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2002-\u200b]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按列表DOM顺序解析姓名、职务和父级人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for node in soup.select(".div1"):
        text = _clean_text(node.get_text(" ", strip=True))
        matched = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})\s+(.+)", text)
        if not matched:
            continue
        name, duty = matched.groups()
        if name in seen_names or not duty:
            continue
        parent_link = node.find_parent("a")
        href = str(parent_link.get("href") or "").strip() if parent_link else ""
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".div1姓名+职务；detail=父级a[href]",
            }
        )
    if not records:
        raise RuntimeError("现任领导列表未解析到人物记录")
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
