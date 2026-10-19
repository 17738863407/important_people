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
    "rule_id": "1418",
    "domain": "lcj.sc.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_forestry_zfld_link_title",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_sichuan_forestry_zfld_link_title_v2",
    "leader_link_selector": "dl.zfld a[href*='/jld/']",
    "name_duty_pattern": r"^([\u4e00-\u9fff·]\s*[\u4e00-\u9fff·]{1,4})\s+(.+)$",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
    },
    "risk_flag": "页面含机构负责人等相邻字段；只解析dl.zfld内人物链接的title文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理全角空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def clean_standalone_concurrent_marker(value: str) -> str:
    """删除独立“兼”状态标记，保留所有具体兼任职务。"""
    cleaned = re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", clean_text(value))
    return re.sub(r"[，,、；;：:]\s*$", "", cleaned).strip()


def split_name_duty(value: str, pattern: re.Pattern[str]) -> tuple[str, str]:
    """从人物链接title中的“姓名 职务”结构切出字段。"""
    match = pattern.match(clean_text(value))
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", match.group(1))
    duty = clean_standalone_concurrent_marker(match.group(2)).strip(" ：:，,。")
    if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
        return "", ""
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导链接DOM顺序提取title中的姓名、职务和人物页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule["url"])
    pattern = re.compile(str(page_rule["name_duty_pattern"]))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for link in soup.select(str(page_rule["leader_link_selector"])):
        source_text = str(link.get("title") or link.get_text(" ", strip=True))
        name, duty = split_name_duty(source_text, pattern)
        if not name:
            continue

        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(source_url, href) if href else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule["parser"]),
                "selector_summary": "dl.zfld内含/jld/的领导链接title及href",
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
