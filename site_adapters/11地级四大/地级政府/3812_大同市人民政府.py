from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3812", "domain": "www.dt.gov.cn", "page_type": "分职务领导照片列表",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_datong_government_v1",
    "leader_region_selector": ".szf_con", "name_selector": ".szf_tit1 a[href] p", "duty_selector": ".szf_tit_l, .szf_tit_l1",
    "detail_link_selector": ".szf_tit1 a[href]", "content_scope": {"start_anchor": "市政府领导", "end_anchor": "", "include_selectors": [".szf_con"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "页面导航区重复领导名单，只取正文照片列表以避免重复", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u2003", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".szf_con")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for group in region.select(".szf_tit1"):
        duty_node = group.select_one(".szf_tit_l, .szf_tit_l1")
        duty = re.sub(r"\s+", "", clean_text(duty_node.get_text(" ", strip=True))).rstrip("：:") if duty_node else ""
        if duty not in {"市长", "副市长", "秘书长"}:
            continue
        for link in group.select("a[href]"):
            name_node = link.select_one("p")
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True))) if name_node else ""
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
                rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", ""))})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
