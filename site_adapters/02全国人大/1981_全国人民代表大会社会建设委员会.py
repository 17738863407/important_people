from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '1981',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '入口页iframe中.right_xinxi',
 'name_selector': '.list1 .font12及职务标题后的.text2',
 'duty_selector': '.list1 .text0与.text1标题',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '入口含多个iframe和大量新闻人物，只接受具有.right_xinxi及主任委员分组结构的iframe',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'risk_note': '从当前入口HTML动态发现iframe，不固定公告或届次名单；姓名括注仅去除性别、民族或单位说明。'}


def _clean_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _split_names(container: object) -> list[str]:
    names: list[str] = []
    paragraphs = container.select("p") or [container]
    for paragraph in paragraphs:
        raw_line = paragraph.get_text("\n", strip=True)
        without_notes = re.sub(r"（[^）]*）", "", raw_line)
        for segment in re.split(r"\s{2,}|\n+", without_notes):
            name = re.sub(r"\s+", "", segment)
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                names.append(name)
    return names


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """动态发现并解析全国人大社会建设委员会组成人员iframe。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy
    from crawler_core.models import PersonRecord

    entry_soup = BeautifulSoup(html, "html.parser")
    member_soup = None
    for iframe in entry_soup.select("iframe[src]"):
        iframe_url = urljoin(final_url, str(iframe.get("src", "")))
        try:
            result = fetch_html_with_strategy(iframe_url, "online")
        except Exception:
            continue
        candidate = BeautifulSoup(result.html, "html.parser")
        if candidate.select_one(".right_xinxi .list1 .font12") and candidate.select_one(".right_xinxi .text1"):
            member_soup = candidate
            break
    if member_soup is None:
        return []

    people: list[tuple[str, str]] = []
    director_group = member_soup.select_one(".right_xinxi .list1")
    if director_group is not None:
        duty_node = director_group.select_one(".text0")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        people.extend((name, duty) for name in _split_names(director_group.select_one(".font12")))
    for heading in member_soup.select(".right_xinxi .text1"):
        duty = _clean_text(heading.get_text(" ", strip=True)).replace("（按姓名笔划为序排列）", "").strip()
        if duty == "委员":
            continue
        names_container = heading.find_next_sibling("div", class_="text2")
        if duty and names_container is not None:
            people.extend((name, duty) for name in _split_names(names_container))

    records = []
    for name, duty in people:
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser="page_parse_page",
                selector_summary="入口iframe .right_xinxi职务姓名分组",
            )
        )
    return records


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
