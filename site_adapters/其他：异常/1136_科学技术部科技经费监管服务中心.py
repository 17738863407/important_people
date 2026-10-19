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
    "rule_id": "1136",
    "page_type": "人物列表完整页",
    "structure_group": "科技部直属单位领导班子列举句",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MostJgzxCurrentLeaderSentenceParser_v4",
    "leader_region_selector": "p:contains(监管中心党支部书记、主任)",
    "name_selector": "监管中心党支部书记、主任及副主任后的姓名列举",
    "duty_selector": "党支部书记、主任及副主任文本标签",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "原独立站失效，采用科技部官网最新完整领导班子列举页；仅匹配当前人物段落中的完整职务列举句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2002-\u200b]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析科技部官网正文中明确列举的监管中心领导班子。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    name_pattern = r"[\u4e00-\u9fff·]{2,5}"
    sentence_pattern = re.compile(
        rf"监管中心(?P<director_duty>党支部书记[、,，]主任|主任)"
        rf"(?P<director>{name_pattern})[,，]"
        rf"副主任(?P<deputies>{name_pattern}(?:[、,，]{name_pattern})*)[,，]"
    )
    leaders: list[tuple[str, str]] = []
    for paragraph in soup.select("p"):
        full_text = _compact_text(paragraph.get_text(" ", strip=True))
        match = sentence_pattern.search(full_text)
        if match is None:
            continue
        director_duty = re.sub(r"[,，]", "；", match.group("director_duty"))
        leaders.append((match.group("director"), director_duty))
        leaders.extend(
            (name, "副主任")
            for name in re.split(r"[、,，]", match.group("deputies"))
            if name
        )
        break

    for name, duty in leaders:
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(rule.get("parser", "")),
                "selector_summary": "科技部官网正文p；监管中心党支部书记、主任姓名及副主任姓名列举句",
            }
        )
    if not records:
        raise RuntimeError("科技部官网正文未解析到监管中心完整领导班子列举句")
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
