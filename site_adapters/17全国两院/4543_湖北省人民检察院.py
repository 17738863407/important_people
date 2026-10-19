from __future__ import annotations
import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4543", "page_type": "领导分组详情页",
    "structure_group": "hubei_procuratorate_grouped_details_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_hubei_procuratorate_v1",
    "leader_region_selector": ".jcygb_ejlist",
    "name_selector": "ul li a[href]", "duty_selector": ".TRS_Editor",
    "detail_link_selector": "ul li a[href]", "detail_strategy": {"required": True, "mode": "detail_page"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析检察长、副检察长及其他院领导、检察委员会专职委员及其他领导、检察委员会委员四个领导分组；委员类人物及职务按网页原序保留，排除部门负责人、员额检察官和专家咨询委员会。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers=headers)
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one(".jcygb_ejlist")
    if region is None:
        raise RuntimeError("未找到人员分组区域 .jcygb_ejlist")

    candidates: list[tuple[str, str]] = []
    for heading in region.select("div.p2"):
        title = clean(heading.get_text(" ", strip=True))
        if title not in {"检察长", "副检察长及其他院领导", "检察委员会专职委员及其他领导", "检察委员会委员"}:
            continue
        name_list = heading.find_next_sibling("ul")
        if name_list is None:
            continue
        for link in name_list.select("li a[href]"):
            name = clean(link.get_text(" ", strip=True))
            if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                candidates.append((name, urljoin(response.url, str(link.get("href") or ""))))

    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        detail = requests.get(detail_url, timeout=30, verify=False, headers=headers)
        detail.raise_for_status()
        detail.encoding = "utf-8"
        detail_soup = BeautifulSoup(detail.text, "html.parser")
        editor = detail_soup.select_one(".TRS_Editor")
        parts = [clean(text) for text in editor.stripped_strings] if editor else []
        parts = [text for text in parts if text]
        duty = next((text for text in parts if text != name and name not in text), "")
        if not duty:
            raise RuntimeError(f"人物详情页缺少可验证的领导职务：{detail_url}")
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail.url,
            "parser": str(page_rule["parser"]),
            "selector_summary": ".jcygb_ejlist目标分组 + 详情页.TRS_Editor",
        })
    if not rows:
        raise RuntimeError("目标领导分组未提取到人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
