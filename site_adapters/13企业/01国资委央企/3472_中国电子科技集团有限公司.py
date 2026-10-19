from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3472",
    "page_type": "人物列表完整页",
    "structure_group": "中国电科可见标题序列人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CetcVisibleHeadingSequenceParser_v2",
    "leader_region_selector": ".leader_items .list h4, .leader_items .list h5",
    "name_selector": "可见标题序列姓名项",
    "duty_selector": "可见标题序列职务项",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务混用h4/h5且含display:none重复块；排除隐藏祖先后按可见标题序列配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


DUTY_KEYWORDS = ("书记", "董事", "总经理", "总会计师", "组长", "党组成员")


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2003\u3000\xa0]+", " ", value).strip().replace("、 ", "、")


def _is_hidden(node) -> bool:
    current = node
    while current is not None and getattr(current, "name", None):
        style = (current.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or current.has_attr("hidden"):
            return True
        if str(current.get("aria-hidden", "")).lower() == "true":
            return True
        current = current.parent
    return False


def _is_duty(value: str) -> bool:
    return any(keyword in value for keyword in DUTY_KEYWORDS)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """排除隐藏重复后，按标题序列配对当前姓名与下一职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".leader_items .list")
    if container is None:
        raise RuntimeError("中国电科领导标题容器不存在")
    records: list[dict] = []
    seen_names: set[str] = set()
    pending_name = ""
    for node in container.select("h4, h5"):
        if _is_hidden(node):
            continue
        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if _is_duty(text):
            name = re.sub(r"\s+", "", pending_name)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                pending_name = ""
                continue
            if name not in seen_names:
                seen_names.add(name)
                records.append(
                    {
                        "name": name,
                        "duty": text,
                        "evidence": text,
                        "detail_url": "",
                        "parser": PAGE_RULE["parser"],
                        "selector_summary": ".leader_items .list可见h4/h5序列；姓名项配对下一职务项",
                    }
                )
            pending_name = ""
        else:
            pending_name = text
    if not records:
        raise RuntimeError("中国电科可见领导标题序列未解析到人物记录")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
