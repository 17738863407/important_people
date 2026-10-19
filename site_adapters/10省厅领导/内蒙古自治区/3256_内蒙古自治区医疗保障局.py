from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3256",
    "domain": "ylbzj.nmg.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "leader_cards_profile_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_inline_leader_cards_profile_current_sentence_v1",
    "leader_card_selector": ".JiGouLingDao_cont .cont ul li",
    "name_selector": ".ldxm span",
    "profile_selector": ".grjl",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "卡片无人物href；只在同卡个人简历内取完整现任句，排除分管工作",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """清理HTML排版空白，并合并中文字符间的标签断开空格。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物卡片顺序提取姓名及同卡简介中的完整现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(str(page_rule.get("leader_card_selector", ""))):
        name_node = card.select_one(str(page_rule.get("name_selector", "")))
        profile = card.select_one(str(page_rule.get("profile_selector", "")))
        if name_node is None or profile is None:
            continue

        name = clean_name(name_node.get_text(" ", strip=True))
        profile_text = clean_text(profile.get_text(" ", strip=True))
        match = re.search(r"现任[^。]*。", profile_text)
        duty = re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", clean_text(match.group(0))) if match else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；card=.JiGouLingDao_cont .cont ul li；"
                    "name=.ldxm span；profile=.grjl；pattern=现任[^。]*。；exclude=.fggz"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
