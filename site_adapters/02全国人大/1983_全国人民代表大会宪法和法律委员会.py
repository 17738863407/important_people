from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1983',
 'page_type': '人物列表完整页',
 'structure_group': 'npc_committee_grouped_members_iframe',
 'reuse_scope': 'single_page',
 'load_mode': 'iframe嵌入',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_npc_grouped_committee_members_v2',
 'leader_region_selector': '.right_xinxi',
 'name_selector': '.font12, .text2 p',
 'duty_selector': '.text0, .text1',
 'detail_link_selector': '',
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_link_selector': None},
 'risk_flag': '人员区位于同页iframe，双字姓名含排版空格',
 'confidence': 'high'}


def _split_group_names(group: object) -> list[str]:
    """以连续全角空格分隔人物，并清除姓名内部排版空格和性别标注。"""
    names: list[str] = []
    for paragraph in group.select("p"):
        raw_text = paragraph.get_text("", strip=False).strip()
        for chunk in re.split(r"\u3000{2,}", raw_text):
            name = re.sub(r"[\s\u3000\u2002\u2003\u00a0]", "", chunk)
            name = re.sub(r"[（(]女[）)]", "", name)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                names.append(name)
    return names


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态发现人员iframe，按主任、副主任、委员三个分组解析。"""
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    member_scope = None
    for iframe in soup.select("iframe[src^='./']"):
        frame_result = fetch_by_raw_requests(urljoin(final_url, str(iframe["src"])))
        frame_soup = BeautifulSoup(frame_result.html, "html.parser")
        candidate = frame_soup.select_one(".right_xinxi")
        if candidate is not None and candidate.select_one(".list1 .text0") is not None:
            member_scope = candidate
            break
    if member_scope is None:
        raise RuntimeError("未发现包含.right_xinxi分组结构的委员会人员iframe")

    rows: list[dict[str, str]] = []

    def add_row(name: str, duty: str) -> None:
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_npc_grouped_committee_members_v2",
            }
        )

    director_duty = member_scope.select_one(".list1 .text0").get_text(" ", strip=True)
    director_name = re.sub(r"[\s\u3000]", "", member_scope.select_one(".list1 .font12").get_text(" ", strip=True))
    director_name = re.sub(r"[（(]女[）)]", "", director_name)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", director_name):
        raise RuntimeError("主任委员姓名字段无效")
    add_row(director_name, director_duty)

    for role_node in member_scope.select(":scope > .text1"):
        duty = role_node.get_text(" ", strip=True)
        duty = re.sub(r"（.*?）", "", duty).strip()
        if duty == "委员":
            continue
        group = role_node.find_next_sibling("div", class_="text2")
        if group is None or duty != "副主任委员":
            continue
        for name in _split_group_names(group):
            add_row(name, duty)
    if len(rows) < 2:
        raise RuntimeError("委员会人员iframe未解析出完整职务分组")
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
