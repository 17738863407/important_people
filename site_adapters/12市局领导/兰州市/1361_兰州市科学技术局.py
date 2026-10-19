from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1361",
    "page_type": "多人物详情合并页",
    "structure_group": "lanzhou_science_bios_and_parenthesized_posts_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_science_bios_and_parenthesized_posts_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "人物简介段首姓名；冒号前括号职务项姓名",
    "duty_selector": "人物简介内完整现任/机构职务句；括号内原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "mixed_biography_paragraphs_and_multi_person_parenthesized_post_lines",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "paragraph_selector": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML正文直接包含6个简介人物和8个括号职务人物，且证据均位于各自人物段落",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def append_row(
    rows: list[dict[str, str]],
    seen_names: set[str],
    name: str,
    duty: str,
    evidence: str,
    page_rule: dict,
    selector_summary: str,
) -> None:
    """校验字段并按正文顺序追加人物。"""
    clean_name = re.sub(r"\s+", "", normalize_space(name))
    clean_duty = normalize_space(duty)
    if (
        not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", clean_name)
        or not clean_duty
        or clean_name in seen_names
    ):
        return
    seen_names.add(clean_name)
    rows.append(
        {
            "name": clean_name,
            "duty": clean_duty,
            "evidence": normalize_space(evidence),
            "detail_url": "",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": selector_summary,
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐段提取简介人物的完整职务句及括号职务人物。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in container.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        if not text:
            continue

        bio_name_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        duty_sentence_match = re.search(r"(?:现任)?兰州市科学技术局[^。]{2,160}。", text)
        if bio_name_match is not None and duty_sentence_match is not None:
            evidence = duty_sentence_match.group(0).removeprefix("现任").removesuffix("。")
            append_row(
                rows,
                seen_names,
                bio_name_match.group("name"),
                evidence,
                evidence,
                page_rule,
                "人物简介段首姓名及同一段内完整现任/机构职务句",
            )
            continue

        if "：" not in text:
            continue
        heading = text.split("：", 1)[0]
        for match in re.finditer(
            r"(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^（）]{2,80})）",
            heading,
        ):
            append_row(
                rows,
                seen_names,
                match.group("name"),
                match.group("duty"),
                match.group("duty"),
                page_rule,
                "冒号前人物项的姓名及括号内原始职务",
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
