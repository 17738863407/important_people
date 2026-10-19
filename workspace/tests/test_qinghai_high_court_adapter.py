from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
ADAPTER_PATH = PROJECT_DIR / "site_adapters" / "17全国两院" / "4431_青海省高级人民法院.py"


def load_adapter():
    spec = importlib.util.spec_from_file_location("adapter_4431", ADAPTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_discovers_leader_article_only_from_court_leader_section() -> None:
    """防止误取法院简介、机构职能等相邻栏目的文章链接。"""
    adapter = load_adapter()
    html = """
    <div class="content">
      <div class="tit_br"><div id="title"><h2>法院简介</h2></div></div>
      <div class="list_br"><a href="/article/detail/1.shtml">法院简介</a></div>
    </div>
    <div class="content">
      <div class="tit_br"><div id="title"><h2>法院领导</h2></div></div>
      <div class="list_br"><a href="/article/detail/2.shtml">省高级法院领导简历</a></div>
    </div>
    """

    assert adapter.discover_leader_article_url(html, "https://qhgy.qhwsfy.gov.cn/index.shtml") == (
        "https://qhgy.qhwsfy.gov.cn/article/detail/2.shtml"
    )


def test_extracts_name_and_current_duty_in_source_order() -> None:
    """防止把性别、学历等简历字段混入姓名或现任职务。"""
    adapter = load_adapter()
    html = """
    <div class="detail"><div class="text">
      <p>姓名：张三</p><p>性别：男</p><p>学历：大学</p>
      <p>现任职务：青海省高级人民法院党组书记、院长</p>
      <p>姓名： 李四</p><p>性别：女</p>
      <p>现任职务： 青海省高级人民法院党组成员、副院长</p>
    </div></div>
    """

    assert adapter.extract_leader_rows(html, {"parser": "test_parser"}) == [
        {
            "name": "张三",
            "duty": "青海省高级人民法院党组书记、院长",
            "evidence": "青海省高级人民法院党组书记、院长",
            "detail_url": "",
            "confidence": "high",
            "parser": "test_parser",
            "selector_summary": ".detail > .text中按姓名与现任职务标签成组",
        },
        {
            "name": "李四",
            "duty": "青海省高级人民法院党组成员、副院长",
            "evidence": "青海省高级人民法院党组成员、副院长",
            "detail_url": "",
            "confidence": "high",
            "parser": "test_parser",
            "selector_summary": ".detail > .text中按姓名与现任职务标签成组",
        },
    ]
