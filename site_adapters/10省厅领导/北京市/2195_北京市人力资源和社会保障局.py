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
    "rule_id": "2195",
    "domain": "rsj.beijing.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "beijing_hrss_photolist_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_hrss_photolist_cards_v1",
    "risk_flag": "页面正文与领导卡片并存，必须限定photolist并从同一卡片读取姓名职务链接",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导照片卡片的DOM原始顺序读取姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".photolist li"):
        name_link = item.select_one("h1 a[href]")
        duty_node = item.select_one("p")
        name = clean_name(name_link.get_text(" ", strip=True) if name_link is not None else "")
        duty = re.sub(r"[（(]挂职[）)]", "", clean_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")).strip(" ，,；;")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        href = clean_text(str(name_link.get("href") or "")) if name_link is not None else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, href) if href else "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".photolist同一卡片h1姓名链接与p职务",
            }
        )
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
