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
    "rule_id": "1764", "page_type": "人物列表完整页", "structure_group": "shenyang_civil_affairs_compound_heading_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_civil_affairs_compound_heading_v2",
    "leader_region_selector": "部门领导标题后的ul.xxgk_rul .qw-list",
    "name_selector": ".yangs首个b中职务结尾边界之后", "duty_selector": ".yangs首个b中职务结尾边界之前",
    "detail_link_selector": ".qw-list直接子a[href]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "职务与姓名无分隔连写；仅按页面已验证职务结尾边界拆分，工作分工必须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


TITLE_PATTERN = re.compile(r"^(?P<duty>.*(?:副局长|局长|组长|书记|巡视员))(?P<name>[\u3400-\u9fff·]{2,4})$")


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按部门领导卡片顺序拆分职务姓名连写标题。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    titles = [node for node in soup.select(".xxgk_tt") if "部门领导" in clean_text(node.get_text(" ", strip=True))]
    if len(titles) != 1:
        raise RuntimeError(f"部门领导标题命中数量异常：{len(titles)}")
    leader_list = titles[0].find_next_sibling("ul")
    if leader_list is None:
        raise RuntimeError("部门领导标题之后缺少列表")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in leader_list.select(".qw-list"):
        heading = card.select_one(".yangs b")
        compact_heading = re.sub(r"\s+", "", clean_text(heading.get_text(" ", strip=True) if heading else ""))
        match = TITLE_PATTERN.fullmatch(compact_heading)
        if match is None:
            raise RuntimeError(f"职务姓名连写标题无法拆分：{compact_heading}")
        name = match.group("name")
        evidence = match.group("duty")
        detail_link = card.find("a", href=True, recursive=False)
        href = clean_text(detail_link.get("href", "") if detail_link else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not detail_url or detail_url == (final_url or page_rule["url"]):
            raise RuntimeError(f"人物详情链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到部门领导卡片")
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
