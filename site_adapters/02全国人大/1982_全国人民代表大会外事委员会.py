from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


SPACE_PATTERN = r"[\s\u00a0\u2000-\u200a\u202f\u3000]"


def clean_text(value: str) -> str:
    """压缩页面排版空白，不改变字段语义。"""
    return re.sub(r"\s+", " ", value or "").strip()


def split_names(value: str) -> list[str]:
    """以两格以上版面空白拆分人员，一格空白视为二字姓名字距。"""
    marked = re.sub(rf"{SPACE_PATTERN}{{2,}}", "|", value or "")
    names: list[str] = []
    for part in marked.split("|"):
        candidate = re.sub(r"（[^）]*）", "", part)
        candidate = re.sub(rf"{SPACE_PATTERN}+", "", candidate)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", candidate):
            names.append(candidate)
    return names


def paragraph_name_blocks(paragraph: Tag) -> list[str]:
    """按段内直接文本与行内标签的实际先后拆成姓名块。"""
    blocks: list[str] = []
    for child in paragraph.children:
        if isinstance(child, NavigableString):
            text = str(child)
        elif isinstance(child, Tag):
            text = child.get_text(" ", strip=True)
        else:
            continue
        if text.strip():
            blocks.append(text)
    return blocks


def direct_text(node: Tag) -> str:
    """读取字段节点直接文本，排除委员排序括注。"""
    return clean_text(" ".join(str(child) for child in node.children if isinstance(child, NavigableString)))


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先明确隐藏的备用 DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def find_members_frame(soup: BeautifulSoup, final_url: str) -> BeautifulSoup:
    """动态检查同源 iframe，返回具有完整三类委员字段的唯一 frame。"""
    matches: list[BeautifulSoup] = []
    for iframe in soup.select("iframe[src]"):
        frame_url = urljoin(final_url, str(iframe.get("src", "")))
        if not same_origin(final_url, frame_url):
            continue
        response = requests.get(
            frame_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145 Safari/537.36"},
            timeout=30,
        )
        response.raise_for_status()
        frame_soup = BeautifulSoup(response.content, "lxml")
        director_duty = frame_soup.select_one(".right_xinxi .list1 .text0")
        group_duties = {
            direct_text(node)
            for node in frame_soup.select(".right_xinxi > .text1")
            if not is_hidden(node)
        }
        if (
            director_duty is not None
            and clean_text(director_duty.get_text(" ", strip=True)) == "主任委员"
            and {"副主任委员", "委员"}.issubset(group_duties)
        ):
            matches.append(frame_soup)
    if len(matches) != 1:
        raise RuntimeError(f"具有完整委员字段的同源 iframe 数量异常：{len(matches)}")
    return matches[0]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析当前外事委员会 iframe 中的三类人员。"""
    soup = BeautifulSoup(html, "lxml")
    frame_soup = find_members_frame(soup, final_url)
    records: list[dict[str, str]] = []
    seen_names: set[str] = set()

    director_duty_node = frame_soup.select_one(".right_xinxi .list1 .text0")
    director_name_node = frame_soup.select_one(".right_xinxi .list1 .font12")
    director_duty = clean_text(director_duty_node.get_text(" ", strip=True) if director_duty_node else "")
    if director_duty != "主任委员" or director_name_node is None:
        raise RuntimeError("主任委员字段结构不完整")
    for name in split_names(director_name_node.get_text(" ", strip=True)):
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": director_duty,
                "evidence": director_duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_npc_foreign_affairs_frame_v1",
            }
        )

    for duty_node in frame_soup.select(".right_xinxi > .text1"):
        if is_hidden(duty_node):
            continue
        duty = direct_text(duty_node)
        if duty == "委员":
            continue
        if duty != "副主任委员":
            continue
        names_box = duty_node.find_next_sibling("div", class_="text2")
        if names_box is None or is_hidden(names_box):
            raise RuntimeError(f"{duty}字段缺少对应名单区域")
        for paragraph in names_box.find_all("p"):
            if is_hidden(paragraph):
                continue
            for block in paragraph_name_blocks(paragraph):
                for name in split_names(block):
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    records.append(
                        {
                            "name": name,
                            "duty": duty,
                            "evidence": duty,
                            "detail_url": "",
                            "confidence": "high",
                            "parser": "page_inline_npc_foreign_affairs_frame_v1",
                        }
                    )
    return records


PAGE_RULE = {
    "rule_id": "1982",
    "page_type": "职务分组名单页",
    "structure_group": "npc_foreign_affairs_members_iframe",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http_with_same_origin_iframe",
    "parser": "page_inline_npc_foreign_affairs_frame_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".right_xinxi",
    "name_selector": ".list1 .font12, .text2 p",
    "duty_selector": ".list1 .text0, .right_xinxi > .text1",
    "detail_link_selector": "",
    "risk_flag": "人员名单位于同源 iframe；二字姓名使用单个全角空格排版，人员间使用两个以上空格",
    "confidence": "high",
}


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
