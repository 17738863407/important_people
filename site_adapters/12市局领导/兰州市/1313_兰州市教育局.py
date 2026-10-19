from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1313",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_education_xml_directory_to_detail_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_education_xml_directory_to_detail_duty_v1",
    "leader_region_selector": "div[id='114138']中的市局领导目录数据",
    "name_selector": "目录记录p",
    "duty_selector": "详情页.main中‘职务’至‘主管工作’之间的字段",
    "detail_link_selector": "目录记录a[href*='art_338_']",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_content_selector": ".main",
        "max_detail_links": 20,
    },
    "risk_flag": "目录数据位于text/xml脚本中，原始职务仅在人物详情页字段中提供",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"[\s\u3000\xa0]+",
        " ",
        str(text or ""),
    ).strip()


def clean_standalone_secondment_marker(text: str) -> str:
    """只删除无期限的独立挂职标记，保留任何带期限的挂职信息。"""
    cleaned = re.sub(r"(?:（挂职）|\(挂职\)|[<＜]挂职[>＞])", "", normalize_space(text))
    return re.sub(r"[，,、；;：:]\s*$", "", cleaned).strip()


def extract_directory_entries(html: str, final_url: str) -> list[tuple[str, str]]:
    """兼容渲染DOM与原始text/xml数据，按当前目录顺序提取人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for link in soup.select("div[id='114138'] li a[href*='art_338_']"):
        name_node = link.select_one("p")
        name = normalize_space(name_node.get_text(" ", strip=True) if name_node else "")
        candidates.append((name, urljoin(final_url, str(link.get("href", "")).strip())))

    if not candidates:
        pattern = re.compile(
            r"<a\s+href=[\"']([^\"']*art_338_[^\"']+)[\"'][^>]*>\s*"
            r"<p>(.*?)</p>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            name = normalize_space(BeautifulSoup(match.group(2), "html.parser").get_text(" ", strip=True))
            candidates.append((name, urljoin(final_url, match.group(1).strip())))

    entries: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for raw_name, detail_url in candidates:
        name = re.sub(r"\s+", "", raw_name)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        entries.append((name, detail_url))
    return entries


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线读取当前人物详情页。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def extract_detail_duty(detail_html: str, expected_name: str) -> str:
    """校验详情页标题姓名并提取明确标注的原始职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".main")
    title = scope.select_one("h1") if scope else None
    if scope is None or title is None:
        return ""
    if re.sub(r"\s+", "", normalize_space(title.get_text(" ", strip=True))) != expected_name:
        return ""
    text = normalize_space(scope.get_text(" ", strip=True))
    match = re.search(r"职\s*务\s+(.+?)\s+主管工作", text)
    return clean_standalone_secondment_marker(
        match.group(1).strip("，,；; ") if match else ""
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持市局领导目录顺序，逐个在线读取详情页职务字段。"""
    entries = extract_directory_entries(html, final_url)
    if not entries:
        raise RuntimeError("当前在线入口未发现可验证的市局领导目录记录")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    rows: list[dict[str, str]] = []
    failed_names: list[str] = []
    for name, detail_url in entries:
        try:
            duty = extract_detail_duty(fetch_detail_html(session, detail_url), name)
        except requests.RequestException:
            duty = ""
        if not duty:
            failed_names.append(name)
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "div[id='114138']目录顺序和动态链接；详情页h1校验姓名后提取职务字段",
            }
        )
    if failed_names:
        raise RuntimeError(f"部分人物详情页未取得可靠职务：{'、'.join(failed_names)}")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
