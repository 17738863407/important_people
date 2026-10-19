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
    "rule_id": "0118",
    "page_type": "人物列表完整页",
    "structure_group": "职务姓名组合标题列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofBeijingLeaderTitleListParser_v2",
    "leader_region_selector": "ul.liBox li a[href]",
    "risk_flag": "领导链接后相邻存在内设处室链接，必须以领导职务结尾边界识别",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一标题中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按列表DOM顺序解析“职务 姓名”组合标题。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(rule["leader_region_selector"]):
        card_text = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?(?:局长|组长|巡视员))\s+([\u4e00-\u9fff·]{2,8})", card_text)
        if not match:
            continue
        duty = _clean_text(match.group(1))
        name = match.group(2)
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "parser": rule["parser"],
                "selector_summary": "ul.liBox领导组合标题；领导职务结尾边界切分",
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
