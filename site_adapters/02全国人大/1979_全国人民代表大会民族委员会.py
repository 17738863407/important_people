from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1979",
    "page_type": "委员会分组名单页",
    "structure_group": "npc_committee_iframe_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "grouped_list",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": "iframe[src]",
    "name_selector": ".right_xinxi .text2 .TRS_Editor p",
    "duty_selector": ".list1 .text0, .right_xinxi > .text1",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "主任委员",
        "end_anchor": "工作委员会",
        "include_selectors": [".right_xinxi .list1", ".right_xinxi > .text1", ".right_xinxi > .text2"],
        "exclude_selectors": [".right_xinxi .text4"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "委员姓名含民族、性别注记和排版空格，姓名仅做注记及空白清理",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """解码实体并压缩普通排版空白。"""
    text = html_lib.unescape(value or "").replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def split_person_tokens(node: Tag) -> list[str]:
    """按名单中的两个以上排版空格拆分同段多人。"""
    tokens: list[str] = []
    for paragraph in node.select(".TRS_Editor p"):
        raw = html_lib.unescape(paragraph.get_text(" ", strip=False)).strip()
        if not raw or re.fullmatch(r"（[^）]+）", raw):
            continue
        marked = re.sub(r"(）)[ \u3000\u00a0]+(?=[\u4e00-\u9fff])", r"\1||", raw)
        marked = re.sub(r"[ \u3000\u00a0]{2,}", "||", marked)
        paragraph_tokens = [token.strip() for token in marked.split("||") if token.strip()]
        index = 0
        while index < len(paragraph_tokens):
            token = paragraph_tokens[index]
            if re.fullmatch(r"（[^）]+）", token):
                index += 1
                continue
            current_name = re.sub(r"\s+|（[^）]*）", "", token)
            if index + 1 < len(paragraph_tokens):
                next_token = paragraph_tokens[index + 1]
                next_name = re.sub(r"\s+|（[^）]*）", "", next_token)
                if len(current_name) == 1 and len(next_name) == 1:
                    tokens.append(f"{token}{next_token}")
                    index += 2
                    continue
            tokens.append(token)
            index += 1
    return tokens


def normalize_name(raw_token: str) -> str:
    """从强结构名单项中移除括号注记和姓名内部排版空白。"""
    name = re.sub(r"（[^）]*）", "", raw_token)
    return re.sub(r"\s+", "", name).strip()


def fetch_people_frame(entry_soup: BeautifulSoup, final_url: str) -> BeautifulSoup:
    """动态发现包含主任委员分组的同站iframe。"""
    for frame in entry_soup.select("iframe[src]"):
        frame_url = urljoin(final_url, str(frame.get("src") or ""))
        response = requests.get(frame_url, timeout=30, verify=False)
        response.raise_for_status()
        frame_soup = BeautifulSoup(response.content.decode("utf-8", errors="ignore"), "html.parser")
        scope = frame_soup.select_one(".right_xinxi")
        if scope is not None and "主任委员" in scope.get_text(" ", strip=True):
            return frame_soup
    raise ValueError("未发现包含主任委员名单的iframe")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按主任委员、副主任委员、委员的网页原始顺序解析名单。"""
    frame_soup = fetch_people_frame(BeautifulSoup(html, "html.parser"), final_url)
    grouped_tokens: list[tuple[str, str]] = []

    director_node = frame_soup.select_one(".right_xinxi .list1 li.font12")
    if director_node is not None:
        raw_director = director_node.get_text("", strip=True)
        raw_director = clean_text(raw_director).replace(" ", "")
        grouped_tokens.append(("主任委员", raw_director))

    for title in frame_soup.select(".right_xinxi > .text1"):
        role = clean_text(title.get_text(" ", strip=True))
        role = re.sub(r"（[^）]*）", "", role).strip()
        if role == "委员":
            continue
        list_node = title.find_next_sibling("div", class_="text2")
        if role != "副主任委员" or list_node is None:
            continue
        grouped_tokens.extend((role, token) for token in split_person_tokens(list_node))

    rows: list[dict[str, str]] = []
    for role, raw_token in grouped_tokens:
        name = normalize_name(raw_token)
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "duty": role,
                "evidence": role,
                "detail_url": "",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
