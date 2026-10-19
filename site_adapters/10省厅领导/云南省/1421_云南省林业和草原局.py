from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1421",
    "page_type": "人物列表完整页",
    "structure_group": "yunnan_forestry_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_forestry_leader_cards_v1",
    "leader_region_selector": ".zfld_layer li p a[href]",
    "name_selector": ".zfld_layer li p a[href]首行",
    "duty_selector": ".zfld_layer li p a[href]其余行",
    "detail_link_selector": ".zfld_layer li p a[href]",
    "content_scope": {
        "start_anchor": "领导专栏首卡",
        "end_anchor": "领导专栏末卡",
        "include_selectors": [".zfld_layer li p a[href]"],
        "exclude_selectors": ["页眉导航", "友情链接", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".zfld_layer li p a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "卡片链接内首行为姓名、其余一至两行为完整职务；多行职务必须按原顺序连接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfld_layer li p a[href]",
            "name_selector": "首个非空文本行",
            "duty_selector": "其余非空文本行",
            "detail_link_selector": "当前卡片href",
            "content_scope": {
                "start_anchor": "领导专栏首卡",
                "end_anchor": "领导专栏末卡",
                "include_selectors": [".zfld_layer li p a[href]"],
                "exclude_selectors": ["页眉导航", "友情链接", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML领导卡片链接直接提供姓名、多行职务和人物详情链接"},
    },
}


def _clean_text(value: str) -> str:
    text = " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    return re.sub(r"[，,]\s*[，,]+", "，", text)


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "zfld_layer" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _detail_url(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, href)
    if resolved.split("#", 1)[0].rstrip("/") == base_url.split("#", 1)[0].rstrip("/"):
        return ""
    parsed = urlparse(resolved)
    return resolved if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".zfld_layer li p a[href]"):
        if _is_hidden(link):
            continue
        parts = [_clean_text(value) for value in link.stripped_strings]
        parts = [value for value in parts if value]
        if len(parts) < 2:
            continue
        name = re.sub(r"\s+", "", parts[0])
        duty = "".join(parts[1:]).strip(" ：:，,。.")
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": _detail_url(base_url, str(link.get("href", ""))),
                "evidence": duty,
                "parser": "custom_yunnan_forestry_leader_cards_v1",
                "selector_summary": ".zfld_layer卡片链接；首行姓名；其余行职务",
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
