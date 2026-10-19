from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


RULE_ID = "1597"


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """统一网页空白字符，保留词语之间必要的单个空格。"""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_member_name(value: str) -> str:
    """清除名单中的空格及性别标记，只保留可验证的姓名。"""
    name = re.sub(r"[（(]\s*女\s*[)）]", "", clean_text(value))
    return name.replace(" ", "")


def parse_name_duty(text: str) -> tuple[str, str] | None:
    """解析主席、副主席人物卡片中的“姓名 职务”文本。"""
    text = clean_text(text)
    match = re.fullmatch(r"(.+?)\s+(常务副主席|副主席|主席)", text)
    if not match:
        return None
    name = clean_member_name(match.group(1))
    duty = clean_text(match.group(2))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
        return None
    return name, duty


def append_record(
    rows: list[dict[str, str]],
    seen: set[tuple[str, str]],
    page_rule: dict,
    base_url: str,
    name: str,
    duty: str,
    detail_url: str,
    evidence: str,
) -> None:
    """按“姓名+职务”去重后追加人物记录，允许同一人具有多个委员身份。"""
    key = (name, duty)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            "organization": str(page_rule.get("organization", "")),
            "url": base_url,
            "name": name,
            "duty": duty,
            "detail_url": detail_url,
            "evidence": evidence,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析主席、副主席及常务委员三类名单。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    root = soup.select_one(".surveycontent")
    if root is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    leader_logo = root.select_one(".ldader_logo")
    if leader_logo is not None:
        text_node = leader_logo.select_one("p")
        link = leader_logo.select_one("a[href]")
        parsed = parse_name_duty(text_node.get_text(" ", strip=True) if text_node else "")
        if parsed:
            name, duty = parsed
            append_record(
                rows,
                seen,
                page_rule,
                base_url,
                name,
                duty,
                urljoin(base_url, link.get("href", "")) if link else "",
                duty,
            )

    for item in root.select("ul.vice-chairman li"):
        text_node = item.select_one("p")
        link = item.select_one("a[href]")
        parsed = parse_name_duty(text_node.get_text(" ", strip=True) if text_node else "")
        if not parsed:
            continue
        name, duty = parsed
        append_record(
            rows,
            seen,
            page_rule,
            base_url,
            name,
            duty,
            urljoin(base_url, link.get("href", "")) if link else "",
            duty,
        )

    for item in root.select(".list_name li"):
        raw_name = clean_text(item.get_text(" ", strip=True))
        name = clean_member_name(raw_name)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
            continue
        append_record(
            rows,
            seen,
            page_rule,
            base_url,
            name,
            "常务委员",
            "",
            "常务委员",
        )
    return rows


def main(page_rule: dict) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    page_rule = {
        "rule_id": RULE_ID,
        "page_type": "人物列表完整页",
        "load_mode": "静态HTML直出",
        "fetch_mode": "raw_http",
        "parser": "page_inline_mmzy_all_leader_groups_v2",
    }
    main(page_rule)
