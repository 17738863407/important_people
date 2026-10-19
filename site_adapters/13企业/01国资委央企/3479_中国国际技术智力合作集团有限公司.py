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
    "rule_id": "3479", "page_type": "职务分组名单页", "structure_group": "ciic_governance_cards",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_direct", "collector": "static_http", "parser": "ciic_governance_cards_v2",
    "leader_region_selector": ".gszlRight .leader li", "name_selector": ".title", "duty_selector": ".short",
    "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "risk_flag": "党委、董事会、经理层跨组重复人物按首次出现顺序动态合并职务",
    "confidence": "high", "profile_reusable": "", "profile_judgement": "",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def normalize_text(value: str) -> str:
    """压缩网页空白。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()
    return re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", text)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析中智集团公司治理三组领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    ordered_names: list[str] = []
    duties_by_name: dict[str, list[str]] = {}

    for card in soup.select(".gszlRight .leader li"):
        name_node = card.select_one(".title")
        duty_node = card.select_one(".short")
        name = normalize_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name and not duty:
            continue
        if not name or not duty:
            raise RuntimeError("治理卡片姓名或职务为空")
        if name not in duties_by_name:
            ordered_names.append(name)
            duties_by_name[name] = []
        if duty not in duties_by_name[name]:
            duties_by_name[name].append(duty)
    if not ordered_names:
        raise RuntimeError("治理卡片选择器未解析到人物")
    return [{"name": name, "duty": "；".join(duties_by_name[name]), "detail_url": "",
             "evidence": "；".join(duties_by_name[name]), "parser": rule["parser"]}
            for name in ordered_names]

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
