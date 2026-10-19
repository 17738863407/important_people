from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1972',
 'page_type': '人物表格页',
 'structure_group': 'npc_committee_iframe_and_grouped_names',
 'reuse_scope': 'page_structure',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_npc_committee_members_v2',
 'leader_region_selector': '#main_c',
 'name_selector': '.text_a, .text_b .TRS_Editor > p',
 'duty_selector': '.tit_a, .tit_b',
 'detail_link_selector': '',
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_link_selector': None},
 'risk_flag': '主任在同页iframe，副主任姓名含单个全角空格拆字',
 'confidence': 'high'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面版面顺序解析iframe主任及正文分组副主任。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#main_c")
    if scope is None or scope.select_one("h1") is None:
        raise RuntimeError("未找到委员会组成人员正文：#main_c")

    rows: list[dict[str, str]] = []
    iframe = scope.select_one("iframe[src*='fzgzzr']")
    if iframe is None or not iframe.get("src"):
        raise RuntimeError("未找到主任信息iframe")
    frame_result = fetch_by_raw_requests(urljoin(final_url, str(iframe["src"])))
    frame = BeautifulSoup(frame_result.html, "html.parser")
    director_scope = frame.select_one(".right")
    if director_scope is None:
        raise RuntimeError("主任iframe缺少.right人物区域")
    director_name = re.sub(r"\s+", "", director_scope.select_one(".text_a").get_text(" ", strip=True))
    director_duty = director_scope.select_one(".tit_a").get_text(" ", strip=True)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", director_name) or not director_duty:
        raise RuntimeError("主任iframe姓名或职务字段无效")
    rows.append(
        {
            "name": director_name,
            "duty": director_duty,
            "evidence": director_duty,
            "detail_url": "",
            "confidence": "high",
            "parser": "page_inline_npc_committee_members_v2",
        }
    )

    deputy_scope = scope.select_one(":scope > .right")
    if deputy_scope is None:
        raise RuntimeError("未找到副主任分组")
    deputy_duty = deputy_scope.select_one(".tit_b").get_text(" ", strip=True)
    for paragraph in deputy_scope.select(".text_b .TRS_Editor > p"):
        raw_text = paragraph.get_text("", strip=False).strip()
        for chunk in re.split(r"[\u3000\u00a0]{2,}", raw_text):
            name = re.sub(r"[\s\u3000\u00a0]", "", chunk)
            name = re.sub(r"[（(]女[）)]", "", name)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            rows.append(
                {
                    "name": name,
                    "duty": deputy_duty,
                    "evidence": deputy_duty,
                    "detail_url": "",
                    "confidence": "high",
                    "parser": "page_inline_npc_committee_members_v2",
                }
            )
    if len(rows) < 2:
        raise RuntimeError("委员会组成人员正文未解析出副主任姓名")
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
