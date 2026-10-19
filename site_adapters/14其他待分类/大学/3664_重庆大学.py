from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3664", "page_type": "职务分组名单页",
    "structure_group": "cqu_current_leader_grouped_list_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "cqu_current_leader_grouped_list_v1",
    "leader_region_selector": ".jl-info1", "name_selector": ".con > ul > li .name",
    "duty_selector": ".con > ul > li .lab", "detail_link_selector": ".name a[href]",
    "content_scope": {"include_selectors": [".jl-info1"], "exclude_selectors": ["[style*='display:none']"]},
    "detail_strategy": {"required": False, "mode": "list_link_optional", "max_detail_links": 50},
    "risk_flag": "党委常委和校长助理为无链接纯文本；并列职务分散在lab子节点；存在隐藏空项",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def _duty_text(node: object) -> str:
    """按节点原始顺序拆分并连接多项职务。"""
    parts: list[str] = []
    for text in node.stripped_strings:
        for item in re.split(r"[、；;]", text):
            item = _clean_text(item)
            if item and item not in parts:
                parts.append(item)
    return "；".join(parts)


def _plain_names(node: object) -> list[str]:
    """按换行拆分无链接名单，并合并姓名内部字距。"""
    chunks = re.split(r"\n+", node.get_text("\n", strip=True))
    names = [_clean_text(chunk) for chunk in chunks]
    return [name for name in names if re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name)]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按可见职务组顺序提取并聚合同一人物的职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".jl-info1")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for group in region.select(".con > ul > li"):
        if "display:none" in str(group.get("style", "")).replace(" ", "").lower():
            continue
        duty_node = group.select_one(":scope > .lab")
        name_node = group.select_one(":scope > .name")
        if duty_node is None or name_node is None:
            continue
        duty = _duty_text(duty_node)
        anchors = name_node.select("a[href]")
        pairs = [(_clean_text(a.get_text(" ", strip=True)), urljoin(final_url, a["href"])) for a in anchors]
        if not pairs:
            pairs = [(name, "") for name in _plain_names(name_node)]
        for name, detail_url in pairs:
            if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            for item in duty.split("；"):
                if item and item not in person["duties"]:
                    person["duties"].append(item)
            if not person["detail_url"] and detail_url:
                person["detail_url"] = detail_url
    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(person["duties"]), detail_url=person["detail_url"],
            evidence="；".join(person["duties"]), confidence="high", parser=page_rule["parser"],
            selector_summary=".jl-info1 .con > ul > li中的.lab与.name",
        ) for name, person in people.items()
    ]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
