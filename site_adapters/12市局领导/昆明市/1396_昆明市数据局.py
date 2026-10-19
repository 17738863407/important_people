from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1396",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_data_bureau_member_lines_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_data_bureau_member_lines_v1",
    "leader_region_selector": "#detail_con",
    "name_selector": "领导班子成员区段段首姓名",
    "duty_selector": "姓名后至冒号、负责或协助前的原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "member_duty_and_responsibility_in_same_paragraph",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#detail_con",
            "start_anchor": "领导班子成员",
            "end_anchor": "内设机构及联系电话",
            "paragraphs": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML机构详情页直接包含领导班子姓名、职务和分工段落",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_member_line(text: str) -> tuple[str, str]:
    """按页面明确分隔符截取段首姓名和原始职务，排除分工内容。"""
    match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})\s+(?P<rest>.+)$", text)
    if not match:
        return "", ""
    duty = re.split(r"[：:]|(?=负责)|(?=协助)", match.group("rest"), maxsplit=1)[0].strip()
    return match.group("name"), duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在标题锚点限定的领导区段内按网页顺序提取。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#detail_con")
    if content is None:
        return []

    in_members = False
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in content.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        if "领导班子成员" in text:
            in_members = True
            continue
        if "内设机构及联系电话" in text:
            break
        if not in_members or not text:
            continue

        name, duty = parse_member_line(text)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
            continue
        if name in seen_names or len(duty) > 80:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#detail_con；领导班子成员至内设机构；段首姓名与分工前职务",
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
