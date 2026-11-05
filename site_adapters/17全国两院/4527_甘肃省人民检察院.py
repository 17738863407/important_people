from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def is_hidden(node: Tag) -> bool:
    """检查人物字段及其祖先，排除明确隐藏的模板内容。"""
    for current in (node, *node.parents):
        if not isinstance(current, Tag):
            continue
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or classes & {"hidden", "hide", "d-none"}:
            return True
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片顺序读取强结构字段，不把下方个人简历混入职务。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = [region for region in soup.select(".leader-list") if not is_hidden(region)]
    if len(regions) != 1:
        raise ValueError("未找到唯一可见的领导列表，需复核页面结构")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in regions[0].select("ul > li"):
        if is_hidden(card):
            continue
        name_node = card.select_one(":scope > .js > .title > a[href]")
        duty_node = card.select_one(":scope > .js > .zhiwu")
        if name_node is None or duty_node is None or is_hidden(name_node) or is_hidden(duty_node):
            raise ValueError("可见领导卡片缺少姓名或职务字段")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        duty = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            raise ValueError("领导卡片的姓名或职务字段不符合预期")
        if name in seen:
            raise ValueError("可见领导卡片出现重复姓名，需人工复核")
        seen.add(name)
        # 详情链接必须来自当前姓名锚点，并符合本站独立文章页路径。
        detail_url = urljoin(final_url, str(name_node.get("href", "")).strip())
        parsed = urlsplit(detail_url)
        if (parsed.scheme not in {"http", "https"} or parsed.netloc != urlsplit(final_url).netloc
                or re.fullmatch(r"/info/\d+/\d+\.htm", parsed.path) is None):
            detail_url = ""
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail_url,
            "source_text": duty_node.get_text(" ", strip=True),
            "method": str(page_rule["parser"]),
        })
    if not rows:
        raise ValueError("领导列表没有可用人物卡片")
    return rows


PAGE_RULE = {
    "rule_id": "4527",
    "page_type": "领导列表强结构卡片页",
    "structure_group": "gansu_procuratorate_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_gansu_procuratorate_leader_cards_v1",
    "detail_strategy": {"required": False, "mode": "name_anchor"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "只读取leader-list内姓名锚点和zhiwu职务字段；下方简历不作为职务字段；保留原始卡片顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """使用统一运行器在线采集并输出十二列结果。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    # 完成十二列结果人工验收前，不提前把本次采集写入公共成功记忆。
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
