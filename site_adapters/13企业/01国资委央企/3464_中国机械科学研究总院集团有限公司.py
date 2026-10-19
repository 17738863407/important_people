from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3464",
    "page_type": "人物列表完整页",
    "structure_group": "机械总院管理团队图片表格行",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CamLeaderTableParser_v2",
    "leader_region_selector": "#divDetail .group-intro table tr:has(img)",
    "name_selector": "td:nth-of-type(2) p:first-of-type",
    "duty_selector": "td:nth-of-type(2) p:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口HTTP当前返回502；强制浏览器取得渲染DOM，仅解析含人物图片的正文表格行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按含图片的正文表格行顺序解析姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for row in soup.select("#divDetail .group-intro table tr"):
        if row.select_one("img") is None:
            continue
        cells = row.select("td")
        if len(cells) < 2:
            continue
        paragraphs = [
            text
            for paragraph in cells[1].select("p")
            if (text := _clean_text(paragraph.get_text(" ", strip=True)))
        ]
        if len(paragraphs) < 2:
            continue
        name = re.sub(r"\s+", "", paragraphs[0])
        evidence = paragraphs[1]
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(rule.get("parser", "")),
                "selector_summary": "#divDetail .group-intro table tr含img；第二td前两非空p为姓名、职务",
            }
        )
    if not records:
        raise RuntimeError("机械总院管理团队表格未解析到人物记录")
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
