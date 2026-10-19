from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0227",
    "page_type": "人物列表完整页",
    "structure_group": "中国侨联现任领导",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_chinaql_current_leaders_v2",
    "leader_region_selector": ".con-left .leader_now",
    "name_selector": ".leader_now_l p a；.leader_now_r h4 + ul a[href]",
    "duty_selector": ".leader_now_l p a首行；.leader_now_r h4",
    "detail_link_selector": ".leader_now a[href]",
    "risk_flag": "秘书长分组当前为空；仅解析含姓名文本的现任领导链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白，并去除姓名中的全角空格。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def split_name_and_note(raw_name: str, group_duty: str) -> tuple[str, str]:
    """从姓名节点剥离性别备注，并将明确兼职标记转存到职务。"""
    compact = clean_text(raw_name).replace(" ", "")
    note_match = re.search(r"[（(]([^）)]+)[）)]", compact)
    notes = note_match.group(1) if note_match else ""
    name = re.sub(r"[（(][^）)]*[）)]", "", compact)
    duty = clean_text(group_duty)
    if "兼职" in notes:
        duty = f"{duty}（兼职）"
    return name, duty


def append_row(
    rows: list[dict],
    page_rule: dict,
    name: str,
    duty: str,
    detail_href: str,
    final_url: str,
) -> None:
    """追加当前强结构人物记录。"""
    name = clean_text(name).replace(" ", "")
    duty = clean_text(duty)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or not duty:
        return
    rows.append(
        {
            "organization": page_rule["organization"],
            "url": page_rule["url"],
            "name": name,
            "duty": duty,
            "detail_url": urljoin(final_url, clean_text(detail_href)) if clean_text(detail_href) else "",
            "evidence": duty,
            "confidence": "high",
            "parser": "page_inline_chinaql_current_leaders_v2",
            "selector_summary": (
                "strategy=custom_parse_page；scope=.con-left .leader_now；"
                "main=.leader_now_l p a；groups=.leader_now_r h4及后续ul人物链接"
            ),
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """解析中国侨联现任领导区，排除历届领导与空分组。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".con-left .leader_now")
    if not isinstance(scope, Tag):
        raise RuntimeError("未定位到中国侨联现任领导区")

    rows: list[dict] = []
    main_link = scope.select_one(".leader_now_l p a[href]")
    if isinstance(main_link, Tag):
        parts = [clean_text(part) for part in main_link.stripped_strings if clean_text(part)]
        if len(parts) >= 2:
            append_row(
                rows,
                page_rule,
                parts[-1],
                "；".join(parts[:-1]),
                str(main_link.get("href") or ""),
                final_url,
            )

    right_scope = scope.select_one(".leader_now_r")
    if isinstance(right_scope, Tag):
        current_duty = ""
        for node in right_scope.find_all(["h4", "a"]):
            if node.name == "h4":
                current_duty = clean_text(node.get_text(" ", strip=True))
                continue
            if not current_duty:
                continue
            raw_name = clean_text(node.get_text(" ", strip=True))
            if not raw_name:
                continue
            name, duty = split_name_and_note(raw_name, current_duty)
            append_row(
                rows,
                page_rule,
                name,
                duty,
                str(node.get("href") or ""),
                final_url,
            )

    if not rows:
        raise RuntimeError("中国侨联现任领导区未抽取到人物")
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
