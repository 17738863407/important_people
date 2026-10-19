from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2427",
    "domain": "sjj.cq.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "chongqing_audit_fzrxx_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_chongqing_audit_fzrxx_cards_v1",
    "leader_region_selector": "ul.jgzn-fzrxx > li",
    "name_selector": ".name",
    "duty_selector": ".job",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "dynamic_from_current_card"},
    "risk_flag": "job节点用多个文本片段排版，须区分并列职务边界与单一职务断行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def join_job_parts(duty_node: Tag) -> str:
    """按页面标点和断行边界还原job节点的完整原始职务。"""
    duty = ""
    for part in (clean_text(text) for text in duty_node.stripped_strings):
        if not part:
            continue
        if not duty:
            duty = part
        elif duty.endswith(("、", "工作")) or part.startswith(("、", "，", "；")):
            duty += part
        else:
            duty += "；" + part
    return duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按负责人卡片顺序解析姓名、完整职务和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in soup.select(str(page_rule["leader_region_selector"])):
        name_node = item.select_one(str(page_rule["name_selector"]))
        duty_node = item.select_one(str(page_rule["duty_selector"]))
        if name_node is None or not isinstance(duty_node, Tag):
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence = join_job_parts(duty_node)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence:
            continue
        link = item.select_one(str(page_rule["detail_link_selector"]))
        detail_url = urljoin(final_url, str(link.get("href") or "")) if link else ""
        key = (name, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
