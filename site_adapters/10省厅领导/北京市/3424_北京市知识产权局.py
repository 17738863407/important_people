from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3424", "domain": "zscqj.beijing.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "beijing_ip_leader_titles_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_ip_leader_titles_v1",
    "risk_flag": "姓名后可能带新闻发言人等页面标签；姓名职务以全角空格分隔，证据保留完整标题",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for title in soup.select(".leaderCon .leader_summ h2"):
        raw = title.get_text(" ", strip=True)
        parts = raw.split("\u3000", 1)
        if len(parts) != 2:
            continue
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})(?:（[^）]+）)?$", parts[0].strip())
        duty = clean_text(parts[1]).rstrip("，,；;。")
        if name_match is None or not duty:
            continue
        # 姓名及其后的“新闻发言人”等页面标签不属于职务字段，保留标题右侧原始职务。
        rows.append({"name": name_match.group("name"), "duty": duty, "detail_url": "", "evidence": duty,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "leader_summ标题全角空格边界及姓名后页面标签"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
