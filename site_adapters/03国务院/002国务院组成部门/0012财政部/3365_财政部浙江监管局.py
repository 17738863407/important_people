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
    "rule_id": "3365",
    "page_type": "人物列表完整页",
    "structure_group": "领导列表职务姓名及独立详情链接",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofZhejiangSupervisionLeaderListParser_v2",
    "leader_region_selector": ".listBox .liBox",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": ".listBox .liBox li a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "列表文本以末尾姓名区分职务，链接为独立人物简介页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导列表DOM顺序抽取职务、姓名及真实人物详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(".listBox .liBox li a[href]")
    if not links:
        raise RuntimeError("未找到领导列表链接 .listBox .liBox li a[href]")

    rows: list[dict] = []
    seen: set[str] = set()
    for link in links:
        evidence = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff]{2,4})", evidence)
        if not match:
            continue
        name = match.group("name")
        if name in seen:
            continue
        seen.add(name)
        duty = re.sub(r"[（(]挂职[）)]", "", _clean_text(match.group("duty"))).strip("，、；; ")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".listBox .liBox li a[href]",
            }
        )

    if not rows:
        raise RuntimeError("领导列表未解析到职务姓名记录")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
