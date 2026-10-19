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
    "rule_id": "4073",
    "domain": "aircas.cas.cn",
    "page_type": "头像与同序文本名单",
    "structure_group": "aircas_current_leader_grid_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_aircas_current_leader_grid_v1",
    "leader_region_selector": ".kty_lm_list .trs_editor_view",
    "name_selector": "人物文本行",
    "duty_selector": "人物文本行",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "头像与姓名职务分处相邻段落，使用正文人物文本行保持版面顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文姓名职务文本的版面顺序解析现任领导。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".kty_lm_list .trs_editor_view")
    if region is None:
        raise RuntimeError("未找到现任领导正文区域 .kty_lm_list .trs_editor_view")

    pattern = re.compile(
        r"(?P<name>[\u4e00-\u9fff·]{2,6})\s*"
        r"(?P<duty>党委书记、副院长|党委副书记、纪委书记|学术院长|副院长|高级专务|院长)"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = paragraph.get_text(" ", strip=True).replace("\u3000", " ").replace("\u2002", " ")
        for match in pattern.finditer(text):
            name = re.sub(r"\s+", "", match.group("name"))
            duty = match.group("duty")
            if name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": str(page_rule["parser"]),
                    "selector_summary": ".kty_lm_list .trs_editor_view p 人物文本行",
                }
            )
    if not rows:
        raise RuntimeError("现任领导正文未解析出姓名职务记录")
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
