from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """合并页面排版空白，不改变正文语义。"""
    return re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先上的明确隐藏标记。"""
    for current in (node, *node.parents):
        if not isinstance(current, Tag):
            continue
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        classes = {str(item).lower() for item in (current.get("class") or [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "hidden" in classes:
            return True
    return False


def remove_excluded_committee_duties(value: str) -> str:
    """整理职务分隔符，保留领导区域中的全部委员职务。"""
    parts = [clean_text(part).strip("，,、；;。 ") for part in re.split(r"[、，,；;]", value)]
    return "、".join(part for part in parts if part)


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按法院领导列表顺序解析标题中由空格分隔的姓名和职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in soup.select("li.fycontentdetail > a[href]"):
        if is_hidden(link):
            continue
        source_text = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.fullmatch(r"(?P<name>[\u3400-\u9fff·]{2,10})\s+(?P<duty>.+)", source_text)
        if match is None:
            continue
        name = match.group("name")
        evidence = remove_excluded_committee_duties(match.group("duty"))
        if not evidence:
            continue
        if name in seen_names:
            raise RuntimeError(f"法院领导列表出现重复人物：{name}")
        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        parsed_detail = urlparse(detail_url)
        parsed_entry = urlparse(final_url)
        if parsed_detail.scheme not in {"http", "https"} or parsed_detail.netloc != parsed_entry.netloc:
            detail_url = ""
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "source_text": source_text,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "li.fycontentdetail按DOM顺序；链接title首个空格分隔姓名与职务",
            }
        )
    if not rows:
        raise RuntimeError("法院领导列表未提取到有效领导记录")
    return rows


PAGE_RULE = {
    "rule_id": "4556",
    "domain": "www.nxfy.gov.cn",
    "page_type": "法院领导列表页",
    "structure_group": "ningxia_high_court_leader_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_ningxia_high_court_leader_list_v1",
    "leader_region_selector": "li.fycontentdetail",
    "name_selector": "li.fycontentdetail > a[title]首个空格前",
    "duty_selector": "li.fycontentdetail > a[title]首个空格后",
    "detail_link_selector": "li.fycontentdetail > a[href]",
    "detail_strategy": {"required": True, "mode": "paired_row_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "严格继承当前在线领导列表，不从其他栏目补名单；领导区域中的委员和专职委员职务完整保留",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
