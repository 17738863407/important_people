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
    "rule_id": "0374", "page_type": "人物列表完整页", "structure_group": "shenyang_finance_leader_link_blocks_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_finance_leader_link_blocks_v2",
    "leader_region_selector": "a[href*='/ldfg/'] .yangs", "name_selector": ".yangs中第一个非空b",
    "duty_selector": ".yangs中第二个非空b", "detail_link_selector": "a[href*='/ldfg/']",
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "领导块后续包含工作分工，必须只读取前两个非空b节点",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按页面领导链接块DOM顺序提取姓名、职务和详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for link in soup.select("a[href*='/ldfg/']"):
        block = link.select_one(".yangs")
        values = [clean_text(node.get_text(" ", strip=True)) for node in block.select("b")] if block is not None else []
        values = [value for value in values if value]
        if len(values) < 2:
            raise RuntimeError("领导链接块缺少姓名或职务节点")
        name, evidence = values[:2]
        detail_url = urljoin(final_url or page_rule["url"], link.get("href") or "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("领导链接块姓名或职务字段异常")
        if name in seen_names or detail_url in seen_urls:
            raise RuntimeError(f"领导链接块人物或链接重复：{name}")
        seen_names.add(name)
        seen_urls.add(detail_url)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到领导链接块")
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
