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
    "rule_id": "0518",
    "page_type": "人物列表完整页",
    "structure_group": "中心简介内领导段落",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "EmicCenterLeadersParser_v2",
    "leader_region_selector": ".detail-content",
    "name_selector": ".detail-content p冒号前",
    "duty_selector": ".detail-content p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP受412限制，需浏览器取得正文；只解析中心领导标题后的姓名职务段落，排除中心职能和简介正文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导标题后的段落顺序抽取姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select(".detail-content p")
    start_index = next(
        (index for index, node in enumerate(paragraphs) if _clean_text(node.get_text(" ", strip=True)) == "中心领导"),
        None,
    )
    if start_index is None:
        raise RuntimeError("中心简介正文未找到中心领导标题")

    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in paragraphs[start_index + 1 :]:
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"([\u4e00-\u9fff·\s]{2,8})[：:]\s*(.+)", evidence)
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        duty = _clean_text(matched.group(2))
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".detail-content；中心领导标题后p；姓名：职务完整段落；排除中心职能与简介正文",
            }
        )
    if not records:
        raise RuntimeError("中心领导标题后未解析到人物记录")
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
