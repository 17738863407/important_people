from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3911",
    "page_type": "详情页异步领导目录",
    "structure_group": "zhangjiakou_government_ajax_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "HTML内嵌异步目录地址",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "api_fragment",
    "collector": "raw_http",
    "parser": "page_inline_zhangjiakou_ajax_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "异步片段ul.info-list",
    "name_selector": "a文本末尾姓名",
    "duty_selector": "a文本姓名前职务",
    "detail_link_selector": "ul.info-list a[href]",
    "api_timeout_seconds": 35,
    "risk_flag": "首屏左侧领导目录为空；必须从当前HTML脚本动态发现zfldLeft片段地址",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def normalized_url(value: str) -> str:
    """统一协议、主机、末尾斜线并移除片段，用于同址判定。"""
    parts = urlparse(value)
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}?{parts.query}".rstrip("?")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """请求当前详情页声明的异步领导目录并按原始顺序解析。"""
    import requests

    base_url = final_url or page_rule["url"]
    endpoint_match = re.search(r"url\s*:\s*['\"]([^'\"]*zfldLeft\.thtml\?[^'\"]+)['\"]", html)
    if endpoint_match is None:
        raise RuntimeError("当前HTML未声明领导目录异步地址")
    endpoint_url = urljoin(base_url, endpoint_match.group(1))

    session = requests.Session()
    session.trust_env = False
    response = session.get(
        endpoint_url,
        timeout=int(page_rule["api_timeout_seconds"]),
        headers={"User-Agent": "Mozilla/5.0", "Referer": base_url},
        verify=False,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "lxml")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in soup.select("ul.info-list li a[href]"):
        label = clean_text(link.get_text(" ", strip=True))
        label_match = re.fullmatch(r"(.+?(?:市长|秘书长))\s+([\u3400-\u9fff·]{2,20})", label)
        if label_match is None:
            continue
        duty = clean_text(label_match.group(1))
        name = label_match.group(2)
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        if normalized_url(detail_url) in {
            normalized_url(page_rule["url"]),
            normalized_url(base_url),
        }:
            detail_url = ""
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "当前HTML动态异步地址；片段ul.info-list li a",
            }
        )

    if not rows:
        raise RuntimeError("异步领导目录未提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
