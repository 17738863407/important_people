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
    "rule_id": "0432",
    "page_type": "跨城市人物表格页",
    "structure_group": "指定城市四套班子表格行",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CeDistrictTargetCityLeaderTableParser_v2",
    "leader_region_selector": ".content .TRS_Editor table",
    "risk_flag": "同一表格含浙江省11市，必须按业务源机构限定单一城市行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一表格排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def _clean_name(value: str) -> str:
    """去除姓名单元格中的兼任括注及排版空白。"""
    text = re.sub(r"[（(]\s*兼\s*[）)]", "", _clean_text(value))
    return "".join(text.split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """只解析运行时业务源所指定城市的一行，继承表格列顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    city_label = str(rule.get("organization") or "").split("—", 1)[0].strip()
    if not city_label:
        return []

    for table in soup.select(rule["leader_region_selector"]):
        table_rows = table.select("tr")
        if not table_rows:
            continue
        headers = [_clean_text(cell.get_text(" ", strip=True)) for cell in table_rows[0].find_all(["th", "td"], recursive=False)]
        if not headers or headers[0] != "各市":
            continue
        for table_row in table_rows[1:]:
            cells = table_row.find_all(["th", "td"], recursive=False)
            if not cells or _clean_text(cells[0].get_text(" ", strip=True)) != city_label:
                continue
            records: list[dict] = []
            for index, cell in enumerate(cells[1:], start=1):
                if index >= len(headers):
                    break
                link = cell.select_one("a[href]")
                raw_name = link.get_text(" ", strip=True) if link else cell.get_text(" ", strip=True)
                name = _clean_name(raw_name)
                evidence = headers[index]
                href = (link.get("href") or "").strip() if link else ""
                if not name or not evidence:
                    continue
                records.append(
                    {
                        "name": name,
                        "duty": evidence,
                        "evidence": evidence,
                        "detail_url": urljoin(base_url, href) if href else "",
                        "parser": rule["parser"],
                        "selector_summary": "浙江省各市表格中业务源指定城市行及对应列标题",
                    }
                )
            return records
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
