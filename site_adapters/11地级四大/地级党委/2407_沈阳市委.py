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
    "rule_id": "2407", "page_type": "人物表格页", "structure_group": "shenyang_party_committee_labeled_tables_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_party_committee_labeled_tables_v2",
    "leader_region_selector": "table.xsy_ldtable", "name_selector": ".yinti0 strong a",
    "duty_selector": ".yinti首个含职务标签p中的a", "detail_link_selector": "当前姓名或职务a[href]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "右栏另含工作分工段；只读取职务标签所在段的a原文",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按表格DOM顺序提取姓名、职务标签字段和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    tables = soup.select("table.xsy_ldtable")
    if not tables:
        raise RuntimeError("当前页面没有市委领导表格")
    records: list[object] = []
    seen_names: set[str] = set()
    for table in tables:
        name_link = table.select_one(".yinti0 strong a[href]")
        duty_paragraphs = [node for node in table.select(".yinti p") if "职务" in re.sub(r"\s+", "", clean_text(node.get_text(" ", strip=True)))]
        if len(duty_paragraphs) != 1:
            raise RuntimeError(f"人物表格职务段命中数量异常：{len(duty_paragraphs)}")
        duty_link = duty_paragraphs[0].select_one("a[href]")
        name = re.sub(r"\s+", "", clean_text(name_link.get_text(" ", strip=True) if name_link else ""))
        evidence = clean_text(duty_link.get_text(" ", strip=True) if duty_link else "")
        evidence = evidence.removesuffix("。").strip()
        href = clean_text((name_link or duty_link).get("href", "") if (name_link or duty_link) else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or not detail_url:
            raise RuntimeError("人物表格姓名、职务或详情链接异常")
        if name_link.get("href") != duty_link.get("href"):
            raise RuntimeError(f"姓名与职务详情链接不一致：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物表格姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
