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
    "rule_id": "2277",
    "page_type": "人物列表完整页",
    "structure_group": "宋庆龄基金会领导成员分组",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sclf_leader_info_groups_v2",
    "leader_region_selector": ".leader-info",
    "name_selector": ".leader-li .leader-cont a[href]",
    "duty_selector": ".leader-li .leader-tit",
    "detail_link_selector": ".leader-cont a[href]",
    "risk_flag": "姓名与职务含字距空格，姓名节点可能附带兼任备注",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def compact_text(value: str) -> str:
    """去除短字段中的全角字距与排版空白。"""
    return re.sub(r"[\s\u3000\u2002\u00a0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按分组DOM顺序解析宋庆龄基金会领导成员。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for group in soup.select(".leader-info .leader-li"):
        title = group.select_one(".leader-tit")
        duty = compact_text(title.get_text(" ", strip=True) if title else "").rstrip("：:")
        if not duty:
            continue
        for link in group.select(".leader-cont a[href]"):
            raw_name = compact_text(link.get_text(" ", strip=True))
            name = re.sub(r"[（(]兼[）)]$", "", raw_name)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                continue
            evidence = duty
            rows.append(
                {
                    "organization": page_rule["organization"],
                    "url": page_rule["url"],
                    "name": name,
                    "duty": evidence,
                    "detail_url": urljoin(final_url, str(link.get("href") or "")),
                    "evidence": evidence,
                    "confidence": "high",
                    "parser": "page_inline_sclf_leader_info_groups_v2",
                    "selector_summary": (
                        "strategy=custom_parse_page；scope=.leader-info；"
                        "group=.leader-li；duty=.leader-tit；name_detail=.leader-cont a[href]"
                    ),
                }
            )
    if not rows:
        raise RuntimeError("宋庆龄基金会领导成员分组未抽取到人物")
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
