from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4021",
    "page_type": "可视化建站领导区块",
    "load_mode": "静态HTML直出",
    "extract_mode": "custom",
    "parser": "custom_cits_absolute_leaders_v2",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "raw_http",
    "detail_strategy": {"required": False, "mode": "dynamic_link"},
    "risk_flag": "以学会领导和联系我们的共同布局容器及坐标限定范围；后添加组件不按DOM位置截断，按人物当前版面顺序输出",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def position(node: object, scope: object = None) -> tuple[int, int]:
    holder = node.find_parent("div", class_="smartAbs")
    top_value, left_value = 0, 0
    while holder is not None and holder is not scope:
        style = holder.get("style", "")
        top = re.search(r"top:\s*(-?\d+)px", style)
        left = re.search(r"left:\s*(-?\d+)px", style)
        if top is None or left is None:
            raise RuntimeError("人物布局组件缺少可验证坐标")
        top_value += int(top.group(1))
        left_value += int(left.group(1))
        if scope is None:
            break
        holder = holder.find_parent("div", class_="smartAbs")
    return top_value, left_value


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    session = requests.Session()
    session.trust_env = False
    response = session.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    html, final_url = response.content.decode("utf-8", errors="replace"), response.url
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".editableContent")
    start = next((block for block in blocks if block.get_text(" ", strip=True) == "学会领导"), None)
    end = next((block for block in blocks if block.get_text(" ", strip=True) == "联系我们"), None)
    if start is None or end is None:
        raise RuntimeError("学会领导或联系我们边界缺失")
    # 可视化建站组件可能后添加，DOM顺序不等于版面顺序。
    # 在两个标题的最近公共布局容器内，以累加的相对坐标确定内容边界。
    scope = next((parent for parent in start.parents if parent.name == "div"
                  and "smartAbs" in parent.get("class", [])
                  and any(parent is ancestor for ancestor in end.parents)), None)
    if scope is None:
        raise RuntimeError("两个标题没有共同的可验证布局容器")
    start_top, end_top = position(start, scope)[0], position(end, scope)[0]
    heading_area = start.find_parent("div", class_="smartAbs").find_parent("div", class_="smartAbs")
    for block in scope.select(".editableContent"):
        area = block.find_parent("div", class_="smartAbs").find_parent("div", class_="smartAbs")
        if (area is not None and area is not scope
                and area.get("ctype") == "area"
                and area.get("cstyle") == heading_area.get("cstyle")
                and area.find_parent("div", class_="smartAbs") is scope):
            candidate_top = position(block, scope)[0]
            if candidate_top > start_top:
                end_top = min(end_top, candidate_top)
    if start_top >= end_top:
        raise RuntimeError("领导区域坐标边界异常")
    leader_blocks = []
    for block in scope.select(".editableContent"):
        hidden = any(node.has_attr("hidden") or str(node.get("aria-hidden", "")).lower() == "true"
                     or set(node.get("class", [])).intersection({"hidden", "hide", "d-none"})
                     or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", str(node.get("style", "")), re.I)
                     for node in (block, *block.parents))
        if not hidden and start_top < position(block, scope)[0] < end_top:
            leader_blocks.append(block)
    titles = {block.get_text(" ", strip=True): position(block, scope)[0] for block in leader_blocks if block.get_text(" ", strip=True) in {"副会长", "副会长兼秘书长"}}
    if set(titles) != {"副会长", "副会长兼秘书长"}:
        raise RuntimeError("领导职务标题缺失")
    rows: list[dict[str, str]] = []
    layout_keys: list[tuple[int, int, int]] = []
    for block in leader_blocks:
        text = re.sub(r"[\s\u00a0\u200b]+", "", block.get_text(" ", strip=True))
        direct = re.fullmatch(r"会长([\u4e00-\u9fff]{2,4})", text)
        name = direct.group(1) if direct else text
        if direct:
            duty = "会长"
        elif name in {"副会长", "副会长兼秘书长"} or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        else:
            top, _ = position(block, scope)
            duty = "副会长兼秘书长" if top > titles.get("副会长兼秘书长", 10**9) else "副会长"
        link = block.select_one("a[href]")
        detail_url = urljoin(final_url, link["href"]) if link else ""
        rows.append({"name":name,"duty":duty,"detail_url":detail_url,"evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"学会领导区块内绝对定位姓名组件"})
        # 左侧会长卡片优先，其后按副会长行从左到右、秘书长下一行读取。
        # DOM组件创建顺序与屏幕顺序不同，必须继承当前组件坐标。
        top, left = position(block, scope)
        group = 0 if direct else (2 if duty == "副会长兼秘书长" else 1)
        layout_keys.append((group, top, left))
    return [row for _, row in sorted(zip(layout_keys, rows), key=lambda pair: pair[0])]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
