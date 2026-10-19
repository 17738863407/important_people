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
    "rule_id": "2609", "page_type": "人物表格页", "structure_group": "shenyang_commerce_labeled_rows_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_commerce_labeled_rows_v2",
    "leader_region_selector": "table.x-table.jgjj_left tr", "name_selector": "人物行第1个td",
    "duty_selector": "人物行td.yinti1内职务标签至分管工作标签", "detail_link_selector": "姓名td a[href]",
    "detail_strategy": {"required": True, "mode": "list_dynamic"},
    "risk_flag": "右栏还含分管工作和办公电话，必须按标签边界排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导表格行顺序解析姓名、原始职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("table.x-table.jgjj_left")
    if len(tables) != 1:
        raise RuntimeError(f"领导工作分工表格数量异常：{len(tables)}")
    records: list[object] = []
    seen_names: set[str] = set()
    for row in tables[0].select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 1:
            continue
        if len(cells) != 2:
            raise RuntimeError(f"人物表格列数异常：{len(cells)}")
        name = clean_text(cells[0].get_text(" ", strip=True))
        duty_area = clean_text(cells[1].get_text(" ", strip=True))
        duty_match = re.fullmatch(r"职\s*务：\s*(.+?)\s*分管工作：.*", duty_area)
        if duty_match is None:
            raise RuntimeError(f"人物行缺少职务与分管工作边界：{name}")
        evidence = clean_text(duty_match.group(1))
        link = cells[0].select_one("a[href]")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or link is None:
            raise RuntimeError("人物行姓名、职务或详情链接异常")
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        if not detail_url or detail_url == final_url:
            raise RuntimeError(f"人物详情链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物表格姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("领导工作分工表格没有有效人物行")
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
