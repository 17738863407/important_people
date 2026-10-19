from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1755",
    "page_type": "人物表格页",
    "structure_group": "hefei_public_leader_table_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "hefei_public_leader_table_v1",
    "leader_region_selector": "#xxgk_lmcon table.xxgk-table-list",
    "name_selector": "td.title-td > a.title[href]冒号后文本",
    "duty_selector": "td.title-td > a.title[href]冒号前文本",
    "detail_link_selector": "td.title-td > a.title[href]",
    "detail_strategy": {
        "required": False,
        "mode": "same_row_independent_detail",
        "same_host_only": True,
    },
    "risk_flag": "入口受JavaScript安全校验保护且列表由浏览器动态渲染，限定机构领导表格并强制浏览器采集",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按机构领导表格DOM原序拆分“职务：姓名”强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#xxgk_lmcon table.xxgk-table-list")
    if region is None:
        raise ValueError("渲染DOM中未找到机构领导表格")
    host = urlparse(final_url).netloc.lower()
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in region.select("tr td.title-td > a.title[href]"):
        raw_text = clean_text(anchor.get("title", "") or anchor.get_text(" ", strip=True))
        if "：" not in raw_text:
            continue
        duty, name = [clean_text(part) for part in raw_text.rsplit("：", 1)]
        name = re.sub(r"\s+", "", name)
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        if urlparse(detail_url).netloc.lower() != host or detail_url == final_url:
            detail_url = ""
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "selector_summary": "#xxgk_lmcon机构领导表格DOM原序；标题按末个中文冒号拆分",
            }
        )
    if not records:
        raise ValueError("机构领导表格未解析到有效人物")
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
