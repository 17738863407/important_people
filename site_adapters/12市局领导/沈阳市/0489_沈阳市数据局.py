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
    "rule_id": "0489", "page_type": "人物表格页", "structure_group": "shenyang_data_leader_table_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_data_leader_table_v2",
    "leader_region_selector": "table.x-table.jgjj_left", "name_selector": "人物行td:first-child a.yinti",
    "duty_selector": "人物行td.yinti1首个p中职务标签后的文本", "detail_link_selector": "人物行td:first-child a.yinti[href]",
    "detail_strategy": {"required": False, "mode": "table_row_link"},
    "risk_flag": "右单元格同时含分管工作，必须只读取首个职务p",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导表格人物行顺序提取姓名、职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("table.x-table.jgjj_left")
    if len(tables) != 1:
        raise RuntimeError("领导表格缺失或命中不唯一")
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for row in tables[0].select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        name_link = cells[0].select_one("a.yinti[href]")
        duty_paragraph = cells[1].find("p", recursive=False)
        if name_link is None or duty_paragraph is None:
            continue
        name = re.sub(r"\s+", "", clean_text(name_link.get_text(" ", strip=True)))
        duty_text = clean_text(duty_paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"职\s*务\s*[：:]\s*(?P<duty>.+)", duty_text)
        evidence = clean_text(match.group("duty")) if match else ""
        detail_url = urljoin(final_url or page_rule["url"], name_link.get("href") or "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物行姓名或职务字段异常")
        if name in seen_names or detail_url in seen_urls:
            raise RuntimeError(f"人物行姓名或详情链接重复：{name}")
        seen_names.add(name)
        seen_urls.add(detail_url)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前领导表格未提取到人物")
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
