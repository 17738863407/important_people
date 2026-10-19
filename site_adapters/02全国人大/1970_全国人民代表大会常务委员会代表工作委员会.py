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

PAGE_RULE = {'rule_id': '1970',
 'page_type': '人物表格页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '#main_c .right',
 'name_selector': '.text_a, .text_b',
 'duty_selector': '.tit_a, .tit_b',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '主任位于委员会组成人员区域的iframe，副主任位于主页面；必须按区域DOM顺序合并',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'risk_note': '姓名间以4个以上排版空格分隔，姓名内部2个排版空格只做清理；（女）标记不是姓名组成部分。'}


def _clean_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析全国人大常委会代表工作委员会组成人员。"""
    from bs4 import BeautifulSoup, Tag
    from crawler_core.fetcher import fetch_by_raw_requests
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#main_c")
    if not main:
        return []

    records: list[object] = []
    seen_names: set[str] = set()

    def append_group(group: Tag) -> None:
        duty_node = group.select_one(".tit_a, .tit_b")
        names_node = group.select_one(".text_a, .text_b")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        raw_names = names_node.get_text("\n", strip=True) if names_node else ""
        if not duty or not raw_names:
            return
        for segment in re.split(r"[\u2002\u2003\u3000\u00a0]{4,}|\n+", raw_names):
            name = re.sub(r"（女）$", "", re.sub(r"\s+", "", segment))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
                continue
            seen_names.add(name)
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
                    selector_summary="#main_c .right职务姓名组",
                )
            )

    for child in main.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "h1" and _clean_text(child.get_text(" ", strip=True)) == "工作委员会":
            break
        if child.name == "iframe" and child.get("src"):
            frame_url = urljoin(final_url, str(child.get("src")))
            frame_result = fetch_by_raw_requests(frame_url)
            frame_soup = BeautifulSoup(frame_result.html, "html.parser")
            for group in frame_soup.select(".right"):
                append_group(group)
        elif "right" in (child.get("class") or []):
            append_group(child)
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
