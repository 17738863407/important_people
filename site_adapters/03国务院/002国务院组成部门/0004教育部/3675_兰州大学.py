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
    "rule_id": "3675", "page_type": "桌面移动双版领导分组页",
    "structure_group": "lzu_leader_groups_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "lzu_leader_groups_v1",
    "leader_region_selector": ".xdld", "name_selector": ".pc-con li a[href], .xdld2 li a[href]",
    "duty_selector": ".pc-con li h3, .xdld2 li h3", "detail_link_selector": ".pc-con li a[href], .xdld2 li a[href]",
    "content_scope": {"include_selectors": [".xdld .pc-con", ".xdld .xdld2"], "exclude_selectors": [".xdld .ph-con"]},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "桌面版与移动版重复；党委常委和校长助理位于桌面主栏之外",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析桌面主栏及其后的常委、校长助理组，排除移动端重复。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".xdld")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    groups = region.select(".pc-con li.flex") + region.select(":scope > .xdld2 li.flex")
    for group in groups:
        title = group.select_one("h3")
        duties = [_compact(part) for part in re.split(r"[、；;]", title.get_text("", strip=True) if title else "")]
        duties = [duty for duty in duties if duty]
        if not duties:
            continue
        for anchor in group.select("p a[href]"):
            name = _compact(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
            person = people.setdefault(name, {"duties": [], "detail_url": detail_url})
            for duty in duties:
                if duty not in person["duties"]:
                    person["duties"].append(duty)
            if not person["detail_url"]:
                person["detail_url"] = detail_url
    return [PersonRecord(
        organization=page_rule["organization"], url=page_rule["url"], name=name,
        duty="；".join(data["duties"]), detail_url=data["detail_url"], evidence="；".join(data["duties"]),
        confidence="high", parser=page_rule["parser"], selector_summary=".xdld桌面主栏与直属.xdld2职务组",
    ) for name, data in people.items()]


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
