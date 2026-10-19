from __future__ import annotations

import re
import sys
from pathlib import Path

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
    """整理现任句分隔符，保留领导区域中的全部委员职务。"""
    parts = [clean_text(part).strip("，,、；;。 ") for part in re.split(r"[、，,；;]", value)]
    return "、".join(part for part in parts if part)


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按“院长之窗”人物卡片的 DOM 顺序提取姓名和当前领导职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    regions = [
        candidate
        for candidate in soup.select(".content > #category.list_br")
        if candidate.select(":scope > .yzzc")
    ]
    if len(regions) != 1:
        raise RuntimeError(f"院长之窗目标区域数量异常：{len(regions)}")
    region = regions[0]

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in region.select(":scope > .yzzc"):
        paragraph = card.select_one(":scope > .fr > p")
        if paragraph is None or is_hidden(card):
            continue
        source_text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"(?P<name>[\u3400-\u9fff·]{2,10})[，,]", source_text)
        duty_match = re.search(r"现任\s*(?P<duty>[^。]+)", source_text)
        if name_match is None or duty_match is None:
            continue
        name = name_match.group("name")
        evidence = remove_excluded_committee_duties(duty_match.group("duty"))
        if not evidence:
            continue
        if name in seen_names:
            raise RuntimeError(f"院长之窗出现重复人物：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "source_text": source_text,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".content内唯一含人物卡片的#category.list_br；现任句；委员类职务完整保留",
            }
        )
    if not rows:
        raise RuntimeError("院长之窗未提取到有效领导记录")
    return rows


PAGE_RULE = {
    "rule_id": "4552",
    "domain": "ln.lncourt.gov.cn",
    "page_type": "院长之窗人物卡片页",
    "structure_group": "ln_high_court_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_ln_high_court_leader_cards_v1",
    "leader_region_selector": ".content > #category.list_br中唯一含.yzzc的容器",
    "name_selector": ".content > #category.list_br > .yzzc > .fr > p首个逗号前",
    "duty_selector": ".content > #category.list_br > .yzzc > .fr > p中的现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "人物段落含简历；只取当前人物卡片的现任句，领导区域中的审判委员会委员、专职委员均保留，页面无人物独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
