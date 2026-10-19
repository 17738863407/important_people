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
    "rule_id": "1028",
    "page_type": "人物列表完整页",
    "structure_group": "第七届理事会领导机构",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_current_huangpu_alumni_council_leaders_v2",
    "leader_region_selector": ".type5",
    "name_selector": ".list-item .sub-list-item a[title]",
    "duty_selector": ".list-item-title",
    "detail_link_selector": ".sub-list-item a[href]",
    "risk_flag": "页面含其他介绍模块，仅解析第七届理事会领导机构.type5",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """去除姓名与短职务中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析第七届理事会领导机构模块。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".type5")
    if scope is None:
        raise RuntimeError("未定位到第七届理事会领导机构模块")

    rows: list[dict] = []
    for group in scope.select(".list-item"):
        title = group.select_one(".list-item-title")
        duty = compact_text(title.get_text(" ", strip=True) if title else "").rstrip("：:")
        if duty not in {"会长", "副会长"}:
            continue
        for link in group.select(".sub-list-item a[href]"):
            name = compact_text(str(link.get("title") or "") or link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                continue
            rows.append(
                {
                    "organization": page_rule["organization"],
                    "url": page_rule["url"],
                    "name": name,
                    "duty": duty,
                    "detail_url": urljoin(final_url, str(link.get("href") or "")),
                    "evidence": duty,
                    "confidence": "high",
                    "parser": "page_current_huangpu_alumni_council_leaders_v2",
                    "selector_summary": (
                        "strategy=custom_parse_page；scope=.type5第七届理事会领导机构；"
                        "group=.list-item；name=.sub-list-item a[title]"
                    ),
                }
            )
    if not rows:
        raise RuntimeError("第七届理事会领导机构未抽取到人物")
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
