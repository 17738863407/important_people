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


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def follow_script_redirects(html: str, source: str) -> tuple[str, str]:
    """按网页自身声明的桌面端相对地址逐级进入当前领导页。"""
    import requests

    current_html, current_url = html, source
    for _ in range(4):
        if re.search(r"id\s*=\s*['\"]leftnav2['\"]", current_html):
            break
        target_match = re.search(r"const\s+url\s*=\s*['\"]([^'\"]+)", current_html)
        target = target_match.group(1) if target_match else ""
        if not target:
            location_targets = re.findall(
                r"window\.location(?:\.href)?\s*=\s*['\"]([^'\"]+)",
                current_html,
            )
            target = location_targets[-1] if location_targets else ""
        if not target:
            break
        target_url = urljoin(current_url, target)
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            target_url,
            timeout=35,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        current_html, current_url = response.text, response.url
    return current_html, current_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从综合领导导航中仅提取“市政府领导”分组。"""
    from bs4 import BeautifulSoup

    source = final_url or str(page_rule.get("url", ""))
    html, source = follow_script_redirects(html, source)
    soup = BeautifulSoup(html, "html.parser")
    government_group = next(
        (
            item
            for item in soup.select("#leftnav2 > li.leftTabLi")
            if clean_text((item.select_one(":scope > div > a") or item).get_text(" ", strip=True))
            == "市政府领导"
        ),
        None,
    )
    rows: list[dict[str, str]] = []
    for group in government_group.select(":scope > ul > li") if government_group else []:
        duty_node = group.find("span", recursive=False)
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        duty = re.sub(r"[\s　:：]+", "", duty)
        for anchor in group.select(":scope > div > a[href]"):
            for hidden in anchor.select("span"):
                hidden.extract()
            name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
            if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            rows.append({
                "name": name,
                "duty": "",
                "evidence": duty,
                "detail_url": urljoin(source, str(anchor.get("href") or "")),
                "confidence": "high",
                "parser": "page_inline_jiujiang_government_group_v1",
            })
    return rows


PAGE_RULE = {
    "rule_id": "3846",
    "page_type": "多级脚本跳转后的综合领导导航",
    "load_mode": "静态HTML含多级脚本跳转",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "grouped_list",
    "parser": "page_inline_jiujiang_government_group_v1",
    "leader_region_selector": "#leftnav2",
    "name_selector": ".leftTabLi li div a[href]",
    "duty_selector": ".leftTabLi li > span",
    "detail_link_selector": ".leftTabLi li div a[href]",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "入口需按网页脚本逐级跳转并排除市委、人大、政协分组",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
