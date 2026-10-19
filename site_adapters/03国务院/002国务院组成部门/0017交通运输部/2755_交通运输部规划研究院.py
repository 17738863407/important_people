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
    "rule_id": "2755",
    "page_type": "人物列表完整页",
    "structure_group": "tpri_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "tpri_leader_cards_v2",
    "leader_region_selector": "div.com_imglist li.post",
    "name_selector": "div.name",
    "duty_selector": "div.job",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "领导团队",
        "end_anchor": "",
        "include_selectors": ["div.com_right div.com_imglist"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "人物卡片链接均为 javascript:doSubmit()，不是可验证的独立详情页，因此详情页链接留空",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "当前页面静态直出 com_imglist，其中每个 li.post 含唯一 name 与 job 字段",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理卡片字段中的排版空白和零宽字符。"""
    return re.sub(r"[\s\u200b-\u200d\ufeff]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导团队卡片的DOM顺序提取姓名和原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.com_right div.com_imglist li.post")
    if not cards:
        raise RuntimeError("未找到领导团队卡片 div.com_imglist li.post")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in cards:
        name_node = card.select_one("div.name")
        duty_node = card.select_one("div.job")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff\u3400-\u4dbf·]{2,8}", name):
            raise RuntimeError(f"领导姓名格式异常：{name or '<空>'}")
        if not duty:
            raise RuntimeError(f"{name} 卡片缺少职务字段 div.job")
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_parse_page",
                "selector_summary": "com_imglist > li.post；div.name姓名；div.job职务",
            }
        )
    return rows


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
