from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3097",
    "page_type": "人物表格页",
    "structure_group": "jilin_govinfo_subcat_jsonp_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_list_to_detail",
    "collector": "raw_http_jsonp",
    "api": {
        "url": "https://infogate.jl.gov.cn/govsearch/jsonp/zf_jd_list.jsp",
        "method": "GET",
        "params": {
            "page": "1",
            "lb": "136485",
            "channelId": "136485",
            "subcat": "2581",
            "callback": "result",
        },
        "page_size": 16,
        "count_field": "num",
        "data_field": "data",
        "name_field": "title",
        "detail_url_field": "puburl",
    },
    "detail_strategy": {
        "required": True,
        "mode": "api_list_to_current_detail",
        "fetch_mode": "raw_http",
        "content_selector": ".contents_div",
        "evidence_pattern": r"现任[^。]*。",
    },
    "risk_flag": "入口表格由公开JSONP接口动态生成；详情正文现任句为原始职务依据",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """确定性压缩网页排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名排版空白及列表标题末尾的说明性括号。"""
    title = re.sub(r"[（(][^（）()]*[）)]\s*$", "", str(value or ""))
    return re.sub(r"[\s\u2000-\u200b\u3000\u00a0]+", "", title)


def fetch_html(url: str, fetch_mode: str) -> str:
    """通过项目公共采集器取得在线文本。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    return fetch_html_with_strategy(url, strategy=fetch_mode).html


def parse_jsonp(text: str, callback: str) -> dict:
    """解析指定回调名包裹的JSONP对象。"""
    match = re.fullmatch(
        rf"\s*{re.escape(callback)}\((\{{.*\}})\)\s*;?\s*",
        str(text or ""),
        flags=re.DOTALL,
    )
    if match is None:
        raise RuntimeError("机构领导JSONP响应格式不符合预期")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise RuntimeError("机构领导JSONP顶层不是对象")
    return payload


def fetch_api_page(api: dict, page: int, fetch_mode: str) -> dict:
    """按页调用当前公开JSONP接口。"""
    params = dict(api["params"])
    params["page"] = str(page)
    api_url = f"{api['url']}?{urlencode(params)}"
    response_text = fetch_html(api_url, fetch_mode)
    return parse_jsonp(response_text, str(params["callback"]))


def extract_current_position(detail_html: str, name: str, strategy: dict) -> str:
    """仅在当前人物详情正文内提取完整现任职务原句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    content = soup.select_one(str(strategy["content_selector"]))
    if content is None:
        return ""
    detail_text = clean_text(content.get_text("", strip=True))
    if not detail_text.startswith(name):
        return ""
    match = re.search(str(strategy["evidence_pattern"]), detail_text)
    if match is None:
        return ""
    evidence = clean_text(match.group(0)).removeprefix("现任").removesuffix("。")
    return re.sub(r"[（(]\s*挂职\s*[）)]", "", evidence).strip(" ，,")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """校验入口技术配置，按JSONP数组顺序解析详情页当前职务。"""
    entry_soup = BeautifulSoup(html, "html.parser")
    api = dict(page_rule["api"])
    api_params = dict(api["params"])
    channel_node = entry_soup.select_one("#trs_js_channelId")
    category_node = entry_soup.select_one(f"#c_{api_params['subcat']}")
    if channel_node is None or str(channel_node.get("value") or "") != str(api_params["channelId"]):
        raise RuntimeError("入口页面频道ID与当前技术配置不一致")
    if category_node is None or clean_text(category_node.get_text(" ", strip=True)) != "机构领导":
        raise RuntimeError("入口页面未确认机构领导类别ID")

    fetch_mode = str(page_rule["fetch_mode"])
    first_payload = fetch_api_page(api, 1, fetch_mode)
    count_field = str(api["count_field"])
    data_field = str(api["data_field"])
    total = int(first_payload.get(count_field) or 0)
    page_size = int(api["page_size"])
    page_count = max(1, math.ceil(total / page_size))
    items = list(first_payload.get(data_field) or [])
    for page in range(2, page_count + 1):
        payload = fetch_api_page(api, page, fetch_mode)
        items.extend(list(payload.get(data_field) or []))
    if total <= 0 or len(items) != total:
        raise RuntimeError(f"机构领导接口总数与数组长度不一致：total={total}, data={len(items)}")

    strategy = dict(page_rule["detail_strategy"])
    name_field = str(api["name_field"])
    detail_url_field = str(api["detail_url_field"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("机构领导接口数组包含非对象记录")
            continue
        title = clean_text(str(item.get(name_field) or ""))
        name = clean_name(title)
        detail_url = str(item.get(detail_url_field) or "").strip()
        detail_path = urlparse(detail_url).path
        subcat = clean_text(str((item.get("tip") or {}).get("subcat") or ""))
        if subcat != "机构领导":
            errors.append(f"{title or '未知记录'}的接口分类不是机构领导")
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            errors.append(f"接口标题不能解析为唯一姓名：{title}")
            continue
        if urlparse(detail_url).netloc != "xxgk.jl.gov.cn" or not re.fullmatch(
            r"/zcbm/fgw_136483/gkml/\d{6}/t\d+_\d+\.html",
            detail_path,
        ):
            errors.append(f"{name}详情链接不符合当前机构领导详情页结构：{detail_url}")
            continue

        try:
            detail_html = fetch_html(detail_url, str(strategy["fetch_mode"]))
            evidence = extract_current_position(detail_html, name, strategy)
        except Exception as error:
            errors.append(f"{name}详情页采集失败：{error}")
            continue
        if not evidence:
            errors.append(f"{name}详情正文未取得完整现任职务原句")
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
            }
        )

    if errors:
        raise RuntimeError("；".join(errors))
    if len(rows) != total:
        raise RuntimeError(f"有效人物数与接口总数不一致：rows={len(rows)}, total={total}")
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
