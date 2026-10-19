from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0906",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_government_home_leader_block_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "harbin_government_home_leader_block_v2",
    "leader_region_selector": ".leader",
    "name_selector": "dl a[href], ul li a[href]",
    "duty_selector": "dl a[href] dd, ul li a[href]",
    "detail_link_selector": "dl a[href], ul li a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "max_detail_links": 20,
    },
    "risk_flag": "站点拒绝无浏览器请求头，online增强HTTP可取得静态领导区块",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市政府领导区块的DOM顺序解析“职务：姓名”链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for link in region.select(page_rule["name_selector"]):
        label = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([^：:]{1,20})[：:]([\u3400-\u9fff·]{2,10})", label)
        if match is None:
            continue
        name = match.group(2)
        if name in seen:
            continue
        seen.add(name)
        evidence = re.sub(r"[（(]挂职[）)]", "", match.group(1)).strip()
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=urljoin(entry_url, link["href"]),
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
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
