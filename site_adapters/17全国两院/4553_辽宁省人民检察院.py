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
    """保留领导卡片现任句中的全部职务，包括各类委员职务。"""
    parts = [clean_text(part).strip("，,、；;。 ") for part in re.split(r"[、，,；;]", value)]
    kept = [
        part
        for part in parts
        if part
    ]
    return "、".join(kept)


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按领导卡片 DOM 顺序提取姓名和全部当前领导职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".leftcot")
    if region is None:
        raise RuntimeError("机构设置页未找到领导区域 .leftcot")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in region.select(":scope .lcot"):
        name_node = card.select_one(":scope > .zw .nam")
        evidence_node = card.select_one(":scope > .jjie > li")
        if name_node is None or evidence_node is None or is_hidden(card):
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        source_text = clean_text(evidence_node.get_text(" ", strip=True))
        duty_match = re.search(r"现任\s*(?P<duty>[^。]+)", source_text)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None or duty_match is None:
            continue
        evidence = remove_excluded_committee_duties(duty_match.group("duty"))
        if not evidence:
            continue
        if name in seen_names:
            raise RuntimeError(f"领导区域出现重复人物：{name}")
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
                "selector_summary": ".leftcot .lcot按DOM顺序；.nam姓名；.jjie li现任句；保留全部委员职务",
            }
        )
    if not rows:
        raise RuntimeError("领导区域未提取到有效领导记录")
    return rows


PAGE_RULE = {
    "rule_id": "4553",
    "domain": "www.ln.jcy.gov.cn",
    "page_type": "机构设置领导卡片页",
    "structure_group": "ln_procuratorate_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态请求跳转异常时由统一链路降级到浏览器渲染",
    "extract_mode": "list_direct",
    "parser": "page_ln_procuratorate_leader_cards_v1",
    "leader_region_selector": ".leftcot",
    "name_selector": ".leftcot .lcot > .zw .nam",
    "duty_selector": ".leftcot .lcot > .jjie > li中的现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "静态请求会跟随错误手机端脚本路径；只解析渲染后.leftcot中的领导卡片，排除右侧内设机构，保留领导卡片中的全部委员职务，页面无人物独立详情链接",
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
