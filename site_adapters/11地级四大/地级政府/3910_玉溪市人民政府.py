from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3910",
    "page_type": "人物详情页内领导目录",
    "structure_group": "yuxi_government_detail_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_yuxi_government_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".leader-list-col",
    "name_selector": "li a[href]冒号后文本",
    "duty_selector": "li a[href]冒号前文本",
    "detail_link_selector": "li a[href]",
    "risk_flag": "入口为常务副市长详情；仅解析标题为市政府领导的目录容器",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def normalized_url(value: str) -> str:
    """统一协议、主机、末尾斜线并移除片段，用于同址判定。"""
    parts = urlparse(value)
    path = parts.path.rstrip("/") or "/"
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}?{parts.query}".rstrip("?")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按市政府领导目录原始顺序提取职务、姓名和详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    region = next(
        (
            node
            for node in soup.select(".leader-list-col")
            if "市政府领导" in clean_text(node.get_text(" ", strip=True))
        ),
        None,
    )
    if region is None:
        raise RuntimeError("未定位到市政府领导目录")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in region.select("ul li a[href]"):
        text_value = clean_text(link.get_text(" ", strip=True))
        parts = re.split(r"[：:]", text_value, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = clean_text(parts[0])
        name = clean_name(parts[1])
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
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
                "selector_summary": ".leader-list-col市政府领导目录ul li a",
            }
        )

    if not rows:
        raise RuntimeError("市政府领导目录未提取到有效人物")
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
