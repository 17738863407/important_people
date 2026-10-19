from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3058",
    "page_type": "领导信息合并展示页",
    "structure_group": "kunming_petition_image_name_duty_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "force_browser": True,
    "browser_render_wait_ms": 3000,
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_petition_image_name_duty_blocks_v2",
    "leader_region_selector": ".activity",
    "name_selector": ".activity img[alt] 的alt属性",
    "duty_selector": "对应图片之后、工作分工标题之前的独立居中段落",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "leader_cards_and_work_divisions_share_article",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".activity",
            "leader_image": "img[alt]",
            "duty_boundary": "下一张领导图片或工作分工标题",
        },
        "api": {
            "enabled": False,
            "reason": "官网渲染正文以领导图片、姓名、职务和工作分工顺序展示",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白，不补全机构前缀。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导图片顺序提取其姓名及工作分工前的独立职务段。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".activity")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for image in region.select("img[alt]"):
        name = normalize_space(image.get("alt", "")).replace(" ", "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) is None or name in seen_names:
            continue

        image_paragraph = image.find_parent("p")
        if image_paragraph is None:
            continue
        evidence = ""
        for paragraph in image_paragraph.find_next_siblings("p"):
            if paragraph.select_one("img[alt]") is not None:
                break
            text = normalize_space(paragraph.get_text(" ", strip=True))
            if not text or text.replace(" ", "") == name:
                continue
            if text == "工作分工":
                break
            evidence = text
            break
        if not evidence:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".activity；img[alt]姓名；工作分工前独立职务段",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
