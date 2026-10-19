from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2682",
    "page_type": "多人物详情合并页",
    "structure_group": "全国台联可见领导分组",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "tailian_visible_leadership_groups_v2",
    "leader_region_selector": ".leadership .leadership-president",
    "name_selector": ".leadership-president-con span；.leadership-president-list a span",
    "duty_selector": ".leadership-president-con h4；相邻.leadership-president-tit",
    "detail_link_selector": ".leadership-president a[href]",
    "risk_flag": "专职副会长列表含CSS display:none备用节点，按页面样式规则排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩排版空白，姓名字段进一步移除字距空格。"""
    return re.sub(r"\s+", " ", value or "").strip()


def compact_name(value: str) -> str:
    """清理姓名中的字距空格。"""
    return re.sub(r"\s+", "", value or "").strip()


def hidden_link_positions(soup: BeautifulSoup, list_id: str) -> set[int]:
    """从当前页面样式中取得指定领导列表被display:none隐藏的链接序号。"""
    hidden: set[int] = set()
    styles = "\n".join(node.get_text("\n") for node in soup.find_all("style"))
    pattern = re.compile(
        rf"#{re.escape(list_id)}\s+a:nth-child\((\d+)\)\s*\{{[^}}]*display\s*:\s*none",
        re.I | re.S,
    )
    for match in pattern.finditer(styles):
        hidden.add(int(match.group(1)))
    return hidden


def group_title(list_node: Tag) -> str:
    """读取列表前一个分组标题的直属文本，排除排序提示子节点。"""
    title = list_node.find_previous_sibling("div", class_="leadership-president-tit")
    if not isinstance(title, Tag):
        return ""
    return clean_text(" ".join(str(node) for node in title.find_all(string=True, recursive=False)))


def make_row(page_rule: dict, final_url: str, name: str, duty: str, href: str) -> dict:
    """构造单条强结构人物记录。"""
    return {
        "organization": page_rule["organization"],
        "url": page_rule["url"],
        "name": name,
        "duty": duty,
        "detail_url": urljoin(final_url, href),
        "evidence": duty,
        "confidence": "high",
        "parser": "tailian_visible_leadership_groups_v2",
        "selector_summary": (
            "strategy=custom_parse_page；scope=.leadership-president；"
            "direct=.leadership-president-con；lists=.leadership-president-list；"
            "hidden=当前style中的display:none序号"
        ),
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按页面可见顺序解析全国台联领导机构。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".leadership .leadership-president")
    if not isinstance(scope, Tag):
        raise RuntimeError("未定位到全国台联领导机构渲染区")

    rows: list[dict] = []
    for card in scope.select("a.leadership-president-con[href]"):
        name_node = card.select_one(".leadership-president-con-right-top span")
        duty_node = card.select_one(".leadership-president-con-right-top h4")
        name = compact_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) and duty:
            rows.append(make_row(page_rule, final_url, name, duty, str(card.get("href") or "")))

    for leader_list in scope.select(".leadership-president-list[id]"):
        list_id = str(leader_list.get("id") or "")
        duty = group_title(leader_list)
        hidden = hidden_link_positions(soup, list_id)
        for position, card in enumerate(leader_list.select(":scope > a[href]"), start=1):
            if position in hidden:
                continue
            name_node = card.select_one("span")
            name = compact_name(name_node.get_text(" ", strip=True) if name_node else "")
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) and duty:
                rows.append(make_row(page_rule, final_url, name, duty, str(card.get("href") or "")))

    if not rows:
        raise RuntimeError("全国台联可见领导分组未抽取到人物")
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
