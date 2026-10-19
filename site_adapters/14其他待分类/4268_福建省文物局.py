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
    "rule_id": "4268",
    "page_type": "领导之窗详情列表",
    "structure_group": "福建省文物局领导之窗当前详情列表",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_fujian_wwj_leaders_v1",
    "leader_region_selector": "[ms-visible='$showStatic(1)']",
    "name_selector": "[ms-visible='$showStatic(1)'] a[href]",
    "duty_selector": "详情标题中姓名前职务",
    "detail_link_selector": "[ms-visible='$showStatic(1)'] a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "页面动态模板仍输出空状态文字，只有领导之窗详情链接可作为人物边界。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从当前领导详情标题解析局内职务、姓名和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for container in soup.find_all(attrs={"ms-visible": "$showStatic(1)"}):
        for link in container.select("a[href]"):
            text = re.sub(r"\s+", "", link.get_text(" ", strip=True))
            role_end = max(text.rfind(marker) + len(marker) for marker in ("局长", "书记", "主任") if marker in text)
            if role_end <= len("福建省文物局"):
                continue
            duty, name = text[len("福建省文物局") : role_end], text[role_end:]
            if not duty or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "领导之窗当前详情标题"})
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
