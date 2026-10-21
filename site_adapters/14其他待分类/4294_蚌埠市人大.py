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
    "rule_id": "4294", "page_type": "人大常委会领导成员正文", "structure_group": "蚌埠市十七届人大常委会领导成员三行名单", "load_mode": "静态HTML直出", "extract_mode": "list_detail", "parser": "page_inline_bengbu_congress_leaders_v1", "leader_region_selector": "当前领导成员文章", "name_selector": "正文主任、副主任、秘书长行", "duty_selector": "正文冒号前职务标题", "detail_link_selector": "入口中标题为当前领导成员的文章链接", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "入口文章摘要元数据与正文不一致，必须以当前发布日期文章的正文为唯一证据。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """读取当前领导成员文章正文的角色—姓名行。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    link = next((item for item in soup.select(".lm_rban a.left[href]") if item.get("title", "").endswith("领导成员")), None)
    if not link:
        return []
    detail_url = urljoin(final_url or str(page_rule["url"]), link["href"])
    session = requests.Session(); session.trust_env = False; session.headers["User-Agent"] = "Mozilla/5.0"
    try:
        response = session.get(detail_url, timeout=20); response.raise_for_status()
    except requests.RequestException:
        return []
    response.encoding = "utf-8"
    detail = BeautifulSoup(response.text, "html.parser")
    body = detail.select_one(".wzcon.j-fontContent")
    if not body:
        return []
    rows: list[dict[str, str]] = []
    for paragraph in body.select("p"):
        text = paragraph.get_text(" ", strip=True).replace("\u3000", " ").replace("\u00a0", "").replace("\u2002", "")
        match = re.match(r"\s*(主\s*任|副主任|秘书长)\s*[：:]\s*(.+)", text)
        if not match:
            continue
        duty = re.sub(r"\s+", "", match.group(1))
        tokens = [re.sub(r"\s+", "", value) for value in re.split(r"\s+", match.group(2).strip())]
        names = [part for token in tokens for part in ((token[:3], token[3:]) if len(token) == 6 else (token,))]
        for name in names:
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": page_rule["parser"], "selector_summary": "当前领导成员正文角色行"})
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
