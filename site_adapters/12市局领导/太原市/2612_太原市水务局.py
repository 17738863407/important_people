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
    "rule_id": "2612",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_water_leader_links_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_water_leader_links_v2",
    "leader_region_selector": ".xxgk_bg",
    "name_selector": "领导分工链接文本末尾姓名",
    "duty_selector": "领导分工链接文本中姓名前完整职务",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": True, "mode": "list_anchor"},
    "risk_flag": "机构概况区域同时含导航和内设机构链接，必须限定href中的领导分工路径",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """合并领导链接文本中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导分工链接DOM顺序解析职务、姓名和独立详情页。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select(".xxgk_bg")
    if len(regions) != 1:
        raise RuntimeError(f"机构概况区域数量异常：{len(regions)}")
    nodes = [a for a in regions[0].select("a[href]") if "/ldfg/" in str(a.get("href", ""))]
    if not nodes:
        raise RuntimeError("机构概况区域没有领导分工链接")
    pattern = re.compile(r"^(?P<evidence>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,10})$")

    records: list[object] = []
    seen_names: set[str] = set()
    for node in nodes:
        text = clean_text(node.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            raise RuntimeError(f"领导链接文本结构异常：{text}")
        name = match.group("name")
        evidence = clean_text(match.group("evidence"))
        detail_url = urljoin(final_url or page_rule["url"], str(node.get("href", "")))
        if name in seen_names or not evidence or detail_url == (final_url or page_rule["url"]):
            raise RuntimeError(f"人物姓名、职务或详情链接异常：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
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
