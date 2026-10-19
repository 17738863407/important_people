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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(
    html: str,
    _final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析合并简介正文中的“职务 + 排版空格 + 姓名”标题段落。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#zoom.j-fontContent")
    if content is None:
        raise ValueError("未找到领导简介正文 #zoom.j-fontContent")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=#zoom.j-fontContent；"
        "row=#zoom.j-fontContent > p[文本结构=职务+两个以上排版空格+姓名]；"
        "detail=none"
    )
    for paragraph in content.find_all("p", recursive=False):
        raw_text = paragraph.get_text(" ", strip=True)
        match = re.fullmatch(
            r"([^：:；;\d]{2,80}?)[\s\u2002\u3000\xa0]{2,}([\u4e00-\u9fff·]{2,8})",
            raw_text,
        )
        if match is None:
            continue
        duty = clean_text(match.group(1))
        name = match.group(2).replace(" ", "")
        if not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_hefei_healthcare_heading_blocks_v1",
                "selector_summary": selector_summary,
            }
        )

    if not rows:
        raise ValueError("领导简介正文未解析出有效职务姓名标题")
    return rows


PAGE_RULE = {
    "rule_id": "3122",
    "page_type": "多人物详情合并页",
    "structure_group": "hefei_healthcare_heading_blocks",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "article_blocks",
    "collector": "browser_dom",
    "parser": "page_inline_hefei_healthcare_heading_blocks_v1",
    "leader_region_selector": "#zoom.j-fontContent",
    "name_selector": "#zoom.j-fontContent > p[文本结构=职务+两个以上排版空格+姓名]",
    "duty_selector": "#zoom.j-fontContent > p[文本结构=职务+两个以上排版空格+姓名]",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP受JavaScript防护拦截；仅解析正文直接子标题段落，排除简历、历史任职、分工与电话",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom.j-fontContent",
            "name_selector": "#zoom.j-fontContent > p[文本结构=职务+两个以上排版空格+姓名]",
            "duty_selector": "#zoom.j-fontContent > p[文本结构=职务+两个以上排版空格+姓名]",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": False,
            "reason": "当前浏览器渲染正文直接提供稳定的职务姓名标题段落",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
