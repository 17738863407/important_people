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
    "rule_id": "4284", "page_type": "市委领导导航详情页", "structure_group": "晋城市委领导左侧分类导航", "load_mode": "静态HTML直出", "extract_mode": "list_detail", "parser": "page_inline_jincheng_party_leaders_v1", "leader_region_selector": ".personnel_box", "name_selector": ".personnel_box .personnel_right a", "duty_selector": ".personnel_box .personnel_type", "detail_link_selector": ".personnel_box .personnel_right a[href]", "detail_strategy": {"required": False, "mode": "list_link"}, "risk_flag": "左侧仅给出分类职务，优先读取对应详情页的完整现职；无 href 人员只保留当前页明确分类职务。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委领导导航顺序抽取人员，并以详情简介补全原始职务证据。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session(); session.trust_env = False; session.headers["User-Agent"] = "Mozilla/5.0"
    base_url = final_url or str(page_rule["url"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in soup.select(".personnel_box > div"):
        role_node = group.select_one(".personnel_type")
        if not role_node:
            continue
        group_duty = re.sub(r"[\s:：]", "", role_node.get_text(" ", strip=True))
        if group_duty in {"书记", "副书记", "常委", "秘书长"}:
            group_duty = "市委" + group_duty
        for link in group.select(".personnel_right a"):
            name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            href = link.get("href", "")
            detail_url = urljoin(base_url, href) if href and not href.startswith("javascript:") else ""
            if detail_url.rstrip("/") == base_url.rstrip("/"):
                detail_url = ""
            duty = group_duty
            if detail_url:
                try:
                    response = session.get(detail_url, timeout=20); response.raise_for_status()
                    response.encoding = response.apparent_encoding or "utf-8"
                    detail = BeautifulSoup(response.text, "html.parser")
                    brief = detail.select_one(".leader_view_brief")
                    if brief:
                        match = re.search(r"现任(.+?)。", re.sub(r"\s+", "", brief.get_text(" ", strip=True)))
                        if match:
                            duty = match.group(1)
                except requests.RequestException:
                    detail_url = ""
            if duty:
                rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": page_rule["parser"], "selector_summary": "市委领导导航 + 当前简介现任句"})
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
