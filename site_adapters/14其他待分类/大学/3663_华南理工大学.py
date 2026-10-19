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
    "rule_id": "3663", "page_type": "多组职务姓名表格页",
    "structure_group": "scut_current_leader_table_v1", "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "browser", "parser": "scut_current_leader_table_v1",
    "leader_region_selector": "#wp_content_w9_0 table", "name_selector": "td a[href], td span",
    "duty_selector": "td", "detail_link_selector": "td a[href]",
    "content_scope": {"include_selectors": ["#wp_content_w9_0 table"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_optional", "max_detail_links": 50},
    "risk_flag": "每行可能含两组职务姓名；党委常委为无链接纯文本名单；二字姓名含全角字距",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _plain_names(cell: object) -> list[str]:
    """拆分无链接名单，保留二字姓名内部的单个全角字距。"""
    raw = cell.get_text("\n", strip=True)
    chunks = re.split(r"(?:[ \xa0]{2,}|\n+)", raw)
    names = [_clean_text(chunk) for chunk in chunks]
    return [name for name in names if re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐行按相邻职务列和姓名列解析，并聚合同一人物职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#wp_content_w9_0 table")
    if table is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for row in table.select("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        for index in range(0, len(cells) - 1, 2):
            duty = _clean_text(cells[index].get_text(" ", strip=True))
            if not duty:
                continue
            name_cell = cells[index + 1]
            anchors = name_cell.select("a[href]")
            pairs = [(_clean_text(a.get_text(" ", strip=True)), urljoin(final_url, a["href"])) for a in anchors]
            if not pairs:
                pairs = [(name, "") for name in _plain_names(name_cell)]
            for name, detail_url in pairs:
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                    continue
                person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
                if duty not in person["duties"]:
                    person["duties"].append(duty)
                if not person["detail_url"] and detail_url:
                    person["detail_url"] = detail_url
    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(person["duties"]), detail_url=person["detail_url"],
            evidence="；".join(person["duties"]), confidence="high", parser=page_rule["parser"],
            selector_summary="#wp_content_w9_0 table行内相邻职务列与姓名列",
        ) for name, person in people.items()
    ]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
