from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """合并页面排版空白，不改变正文语义。"""
    text = re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()
    return re.sub(r"\s*([，,、；;：:。])\s*", r"\1", text)


def extract_card_duty(card_text: str, name: str, role: str) -> str:
    """从当前人物卡片简介首句提取带完整机构名称的现职。"""
    sentences = [clean_text(item) for item in re.split(r"[。]", card_text) if clean_text(item)]
    candidates: list[str] = []
    for sentence in sentences:
        if name not in sentence or role not in sentence:
            continue
        match = re.search(
            rf"{re.escape(name)}[，,](?:男|女)[，,][^，,。]+[，,](?P<duty>[^。]+?{re.escape(role)})$",
            sentence,
        )
        if match is not None:
            candidates.append(clean_text(match.group("duty")))
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise RuntimeError(f"人物卡片完整现职候选数量异常：{name}，{len(unique)}")
    return unique[0]


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按人物卡片 DOM 顺序提取姓名和简介中的完整现职。"""
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for intro in soup.select("p.simpleintro"):
        name_node = intro.select_one(".leadername")
        role_node = intro.select_one(".leaderpost")
        if name_node is None or role_node is None or intro.parent is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        role = clean_text(role_node.get_text(" ", strip=True)).strip("()（） ")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None or not role:
            continue
        if name in seen_names:
            raise RuntimeError(f"领导简介页面出现重复姓名：{name}")
        duty = extract_card_duty(clean_text(intro.parent.get_text(" ", strip=True)), name, role)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "人物卡片姓名节点及同卡片简介首句中的完整现职",
            }
        )
        seen_names.add(name)
    if not rows:
        raise RuntimeError("领导简介页面未提取到人物卡片")
    return rows


PAGE_RULE = {
    "rule_id": "4488",
    "page_type": "税务机关领导简介人物卡片",
    "structure_group": "chinatax_county_leader_cards_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "浏览器渲染在线页面",
    "extract_mode": "structured_cards",
    "parser": "page_chinatax_county_leader_cards_v1",
    "leader_region_selector": "领导简介页 p.simpleintro 所属人物卡片",
    "name_selector": ".leadername",
    "duty_selector": "同卡片简介首句中与 .leaderpost 对应的完整现职",
    "detail_link_selector": "页面未提供独立人物详情链接，留空",
    "detail_strategy": {"required": False, "mode": "same_page_profile_card"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "页面无人物详情链接；只在姓名、职务标签和简介正文同属一个人物卡片时抽取，并排除后续分工句",
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
