from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0885",
    "page_type": "多人物详情合并页",
    "structure_group": "hangzhou_party_committee_sidebar_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "hangzhou_party_committee_sidebar_detail_v1",
    "leader_region_selector": ".sidenav .col_list",
    "name_selector": "li > a姓名前缀",
    "duty_selector": ".profession_name现任职务或侧栏原始职务",
    "detail_link_selector": "li > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_sidebar_links",
        "same_host_only": True,
        "detail_name_selector": ".profession_name .name",
        "detail_duty_selector": ".profession_name",
    },
    "risk_flag": "侧栏含政府领导跳转且个别人物使用机构主页占位，严格限定市委领导ul并逐页验证姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


DUTY_START_PATTERN = re.compile(r"^(省委常委|副书记|常委)$")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compact_name(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip()


def split_sidebar_text(value: str) -> tuple[str, str]:
    """以侧栏可验证的职务起始词为边界拆分姓名和职务。"""
    parts = clean_text(value).split(" ")
    duty_index = next(
        (index for index, part in enumerate(parts) if DUTY_START_PATTERN.fullmatch(part)),
        -1,
    )
    if duty_index <= 0:
        return "", ""
    return compact_name(" ".join(parts[:duty_index])), " ".join(parts[duty_index:])


def extract_detail_fields(html: str) -> tuple[str, str]:
    """提取详情页现任职务强结构，不扫描简历或活动正文。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".profession_name")
    name_node = region.select_one(".name") if region else None
    if region is None or name_node is None:
        return "", ""
    raw_name = clean_text(name_node.get_text(" ", strip=True))
    name = compact_name(raw_name)
    full_text = compact_name(region.get_text("", strip=True))
    duty = full_text[len(name) :].strip() if full_text.startswith(name) else ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委领导侧栏原序解析，并动态核验真实人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    entry_host = urlparse(final_url).netloc.lower()
    entry_path = urlparse(final_url).path.rstrip("/")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    records: list[dict[str, str]] = []

    for anchor in soup.select(".sidenav .col_list > li > a[href]"):
        name, sidebar_duty = split_sidebar_text(anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not sidebar_duty:
            continue

        candidate_url = urljoin(final_url, anchor.get("href", ""))
        parsed = urlparse(candidate_url)
        detail_url = ""
        evidence = sidebar_duty

        if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == entry_host:
            candidate_path = parsed.path.rstrip("/")
            if candidate_path and candidate_path != "/":
                if candidate_path == entry_path:
                    detail_name, detail_duty = extract_detail_fields(html)
                else:
                    try:
                        response = session.get(candidate_url, timeout=30)
                        response.raise_for_status()
                        response.encoding = response.apparent_encoding or "utf-8"
                        detail_name, detail_duty = extract_detail_fields(response.text)
                    except requests.RequestException:
                        detail_name, detail_duty = "", ""
                if detail_name == name and detail_duty:
                    evidence = detail_duty
                    if candidate_path != entry_path:
                        detail_url = candidate_url

        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "selector_summary": ".sidenav市委领导侧栏原序；.profession_name姓名与现任职务逐页核验",
            }
        )

    if not records:
        raise ValueError("未在市委领导侧栏中解析到有效人物")
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
