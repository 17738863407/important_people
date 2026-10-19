from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


SPACE_PATTERN = r"[\s\u00a0\u2000-\u200a\u202f\u3000]"


def clean_text(value: str) -> str:
    """压缩普通排版空白，保留原始中文文本。"""
    return re.sub(r"\s+", " ", value or "").strip()


def split_names(value: str) -> list[str]:
    """按名单空白和民族、性别括注边界拆分姓名。"""
    marked = re.sub(rf"）{SPACE_PATTERN}*", "）|", value or "")
    marked = re.sub(rf"{SPACE_PATTERN}{{3,}}", "|", marked)
    names: list[str] = []
    for part in marked.split("|"):
        candidate = re.sub(r"（[^）]*）", "", part)
        candidate = re.sub(rf"{SPACE_PATTERN}+", "", candidate)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", candidate):
            names.append(candidate)
    return names


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先明确隐藏的备用内容。"""
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


def paragraph_name_blocks(paragraph: Tag) -> list[str]:
    """保留段内直接文本与行内标签的页面顺序，避免相邻姓名粘连。"""
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


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def parse_director_iframe(soup: BeautifulSoup, final_url: str) -> list[dict[str, str]]:
    """动态检查同源 iframe，仅接受含明确主任委员字段的 frame。"""
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
        duty_node = frame_soup.select_one(".right .tit_a")
        name_node = frame_soup.select_one(".right .text_a")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if duty != "主任委员" or name_node is None or is_hidden(name_node):
            continue
        names = split_names(name_node.get_text(" ", strip=True))
        if not names:
            raise RuntimeError("主任委员 iframe 未解析到合规姓名")
        return [
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_npc_qualification_groups_v1",
            }
            for name in names
        ]
    raise RuntimeError("未找到含明确主任委员字段的同源 iframe")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析主任委员 iframe 及主页面副主任委员分组，排除末尾普通委员名单。"""
    soup = BeautifulSoup(html, "lxml")
    right = soup.select_one("#main_c_dbzg > .right")
    if right is None:
        raise RuntimeError("未找到代表资格审查委员会主名单区域")

    records = parse_director_iframe(soup, final_url)
    seen_names = {record["name"] for record in records}
    current_duty = ""
    for child in right.find_all("div", recursive=False):
        classes = set(child.get("class", []))
        if "tit_b" in classes:
            current_duty = clean_text(child.get_text(" ", strip=True))
            if current_duty != "副主任委员":
                current_duty = ""
            continue
        if "text_b" not in classes or not current_duty or is_hidden(child):
            continue
        for paragraph in child.find_all("p"):
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
                            "duty": current_duty,
                            "evidence": current_duty,
                            "detail_url": "",
                            "confidence": "high",
                            "parser": "page_inline_npc_qualification_groups_v1",
                        }
                    )
    return records


PAGE_RULE = {
    "rule_id": "1971",
    "page_type": "职务分组名单页",
    "structure_group": "npc_qualification_groups_with_director_iframe",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http_with_same_origin_iframe",
    "parser": "page_inline_npc_qualification_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "#main_c_dbzg > .right",
    "name_selector": ".text_a, .text_b p",
    "duty_selector": ".tit_a, .tit_b",
    "detail_link_selector": "",
    "risk_flag": "主任委员位于同源 iframe；姓名含民族、性别括注及用于排版的 Unicode 空格",
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
