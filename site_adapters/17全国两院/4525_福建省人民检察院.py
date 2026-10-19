from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_target_duty(value: str) -> str:
    """保留院领导区域展示的全部职务，包括各类委员职务。"""
    pieces = [clean_text(item).strip("，,。；; ") for item in re.split(r"[、，,；;]", value)]
    return "、".join(item for item in pieces if item)


def extract_detail_duty(html: str, name: str) -> str:
    """从当前人物详情正文的姓名后首个职务行提取现职。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".wzzw, .view.TRS_UEDITOR, .view")
    if region is None:
        return ""
    texts = [clean_text(node.get_text(" ", strip=True)) for node in region.select("p")]
    for text in texts:
        if re.search(r"检察长|副检察长|政治部主任|纪检监察组组长|党组", text):
            value = text.removeprefix(name).lstrip("，,:： ")
            return clean_target_duty(value)
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按院领导列表原序提取链接标题，缺失职务时在线回取当前详情。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html or "", "html.parser")
    links = soup.select("td.bor_4 a.b14[href]")
    if not links:
        raise RuntimeError("未找到院领导列表链接 td.bor_4 a.b14[href]")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in links:
        text = clean_text(link.get_text(" ", strip=True))
        parts = re.split(r"[：:]", text, maxsplit=1)
        name = clean_text(parts[0]).replace(" ", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        duty = clean_target_duty(parts[1]) if len(parts) == 2 else ""
        if not duty:
            detail = fetch_html_with_strategy(detail_url, strategy="requests", timeout=30, referer=final_url)
            duty = extract_detail_duty(detail.html, name)
            detail_url = detail.final_url
        if not duty:
            raise RuntimeError(f"人物 {name} 未找到可验证的领导职务")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "院领导链接原序；冒号前姓名、后为职务；无职务项回取同次人物详情；保留全部委员职务",
            }
        )
        seen.add(name)
    if not rows:
        raise RuntimeError("院领导列表未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4525",
    "domain": "www.fj.jcy.gov.cn",
    "page_type": "院领导链接列表",
    "structure_group": "fujian_procuratorate_leader_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出，首项必要时请求详情",
    "extract_mode": "list_to_detail",
    "parser": "page_fujian_procuratorate_leader_links_v1",
    "leader_region_selector": "td.bor_4中的院领导列表",
    "name_selector": "a.b14链接文本冒号前",
    "duty_selector": "a.b14链接文本冒号后或详情正文姓名后首个职务行",
    "detail_link_selector": "a.b14[href]",
    "detail_strategy": {"required": False, "mode": "missing_duty_to_detail", "detail_collector_type": "requests"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "首项列表只显示姓名，需回取详情；院领导区域内检委会委员、专职委员等人物及职务全部保留",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
