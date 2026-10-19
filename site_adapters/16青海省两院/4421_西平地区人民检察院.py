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
    "rule_id": "4421",
    "page_type": "领导人物卡片列表",
    "structure_group": "qinghai_procuratorate_leader_rows_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "custom_parse_page",
    "parser": "qinghai_procuratorate_leader_rows_v1",
    "leader_region_selector": ".mol_contents",
    "name_selector": ".mol_contents_row > .mol_contents_L > span",
    "duty_selector": ".mol_contents_row > .mol_contents_L首个文本字段",
    "detail_link_selector": ".mol_contents_row > .mol_contents_r > a.btnMore[href]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "站点HTTPS证书主机名不匹配；静态HTML卡片字段完整，需由采集链路执行受控SSL降级",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按卡片DOM顺序提取左栏姓名、职务及右栏人物详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".mol_contents > .mol_contents_row")
    records: list[object] = []
    seen_names: set[str] = set()
    source_url = final_url or str(page_rule.get("url", ""))

    for card in cards:
        left = card.select_one(":scope > .mol_contents_L")
        name_node = left.select_one(":scope > span") if left else None
        field_lines = [clean_text(value) for value in left.stripped_strings] if left else []
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = field_lines[0] if len(field_lines) == 2 else ""
        detail_node = card.select_one(":scope > .mol_contents_r > a.btnMore[href]")
        href = clean_text(detail_node.get("href", "") if detail_node else "")
        detail_url = urljoin(source_url, href) if href else ""

        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            raise RuntimeError("人物卡片姓名字段异常")
        if not evidence:
            raise RuntimeError(f"人物卡片职务字段异常：{name}")
        if not detail_url or detail_url == source_url:
            raise RuntimeError(f"人物详情链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片姓名重复：{name}")

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

    if not records:
        raise RuntimeError("当前页面未提取到领导人物卡片")
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
