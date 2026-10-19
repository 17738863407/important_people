from __future__ import annotations

import json
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面的DeepSeek图片视觉解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule

    page_rule = build_vision_page_rule(
        rule_id,
        "img[src*='/upload/image/']",
        "只抽取中心领导图片中明确出现的姓名及当前职务，按图片版面顺序输出。",
    )
    page_rule["source_api_url"] = (
        "https://api.ncosm.org.cn/Admin/Api/organizationdetail?type=3"
    )
    return page_rule


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """运行DeepSeek V4 Flash视觉抽取和证据解析。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_by_requests
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings

    selector = str(page_rule["leader_region_selector"])
    if not BeautifulSoup(html, "html.parser").select(selector):
        api_url = str(page_rule["source_api_url"])
        api_result = fetch_by_requests(
            api_url,
            timeout=get_settings().request_timeout_seconds,
        )
        response = json.loads(api_result.html)
        content = str(response.get("data", {}).get("content") or "")
        if not content:
            raise RuntimeError("中心领导业务接口未返回图片内容")
        html = content.replace('src="http://', 'src="https://')
        final_url = api_result.final_url
    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def main(rule_id: str) -> None:
    """运行当前图片人物脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(build_page_rule(rule_id), globals(), project_dir / "outputs")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1844"
    main(rule_id_value)
