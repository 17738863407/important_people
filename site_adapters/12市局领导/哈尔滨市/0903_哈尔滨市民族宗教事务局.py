from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "0903",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_kaiti_name_following_duty",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "楷体独立姓名节点",
    "duty_selector": "姓名节点后的首个非空段落",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "以姓名节点和相邻职务段落绑定，排除后续负责、分管内容",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def is_name_node(node: Tag) -> bool:
    text = clean_text(node.get_text("", strip=True)).replace(" ", "")
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text):
        return False
    styled_nodes = [node, *node.find_all(style=True)]
    return node.name == "h1" or any("楷体" in str(item.get("style", "")) for item in styled_nodes)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#detailContent")
    if region is None:
        raise ValueError("未找到领导信息正文 #detailContent")
    blocks = [child for child in region.children if isinstance(child, Tag) and child.name in {"h1", "p"}]
    rows: list[dict[str, str]] = []
    for index, block in enumerate(blocks):
        if not is_name_node(block):
            continue
        name = clean_text(block.get_text("", strip=True)).replace(" ", "")
        duty = ""
        for following in blocks[index + 1 :]:
            if is_name_node(following):
                break
            following_text = clean_text(following.get_text("", strip=True))
            if not following_text:
                continue
            duty = following_text
            break
        if not duty or re.match(r"^(?:负责|分管|联系)", duty):
            raise ValueError(f"姓名节点后未取得可靠原始职务：{name}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "#detailContent楷体姓名节点及相邻首个非空职务段落",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现可验证的姓名职务块")
    return rows


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
