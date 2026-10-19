from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


PAGE_RULE = {
    "rule_id": "3921",
    "page_type": "栏目元数据驱动接口列表",
    "structure_group": "ziyang_government_channel_api_v1",
    "reuse_scope": "single_page",
    "load_mode": "JavaScript接口渲染",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "api_json",
    "collector": "raw_http",
    "parser": "page_inline_ziyang_government_api_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "channelsTagSelf.children",
    "name_selector": "接口results[].title",
    "duty_selector": "当前子栏目name",
    "detail_link_selector": "接口redirectUrl或urls.pc",
    "api_path": "/searchManuscript",
    "api_timeout_seconds": 35,
    "risk_flag": "首屏领导容器为空；必须从当前HTML栏目元数据取得组ID后调用公开接口",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """读取当前栏目元数据，按子栏目顺序请求人物接口。"""
    import requests

    metadata_match = re.search(r"var\s+channelsTagSelf\s*=\s*(\{.*?\});\s*//当前栏目信息", html, re.S)
    if metadata_match is None:
        raise RuntimeError("当前HTML未包含政府领导栏目元数据")
    channel_data = json.loads(metadata_match.group(1))
    groups = channel_data.get("children") or []
    if not groups:
        raise RuntimeError("政府领导栏目元数据没有子栏目")

    base_url = final_url or page_rule["url"]
    endpoint_url = urljoin(base_url, page_rule["api_path"])
    session = requests.Session()
    session.trust_env = False
    rows: list[dict] = []
    seen_names: set[str] = set()
    for group in groups:
        if int(group.get("showOrNot", 0)) != 1:
            continue
        duty = clean_text(group.get("name") or group.get("describes"))
        code = clean_text(group.get("code"))
        channel_id = clean_text(group.get("id"))
        if not duty or not code or not channel_id:
            continue
        response = session.post(
            endpoint_url,
            data={
                "current": 1,
                "pageSize": 20,
                "channelCode[]": code,
                "webSiteCode[]": "zysrmzf",
                "channelTreeIds[]": channel_id,
            },
            timeout=int(page_rule["api_timeout_seconds"]),
            headers={"User-Agent": "Mozilla/5.0", "Referer": base_url},
            verify=False,
        )
        response.raise_for_status()
        results = ((response.json().get("data") or {}).get("results") or [])
        for item in results:
            name = clean_name(item.get("title"))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
                continue
            redirect_url = clean_text(item.get("redirectUrl"))
            if redirect_url:
                detail_url = urljoin(base_url, redirect_url)
            else:
                urls_value = item.get("urls") or "{}"
                urls = json.loads(urls_value) if isinstance(urls_value, str) else urls_value
                detail_url = urljoin(base_url, clean_text(urls.get("pc")))
            if urlparse(detail_url).scheme not in {"http", "https"}:
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
                    "selector_summary": "channelsTagSelf子栏目顺序；searchManuscript接口results",
                }
            )

    if not rows:
        raise RuntimeError("政府领导公开接口未返回有效人物")
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
