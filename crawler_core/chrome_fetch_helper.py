from __future__ import annotations

import argparse
import json
import sys
import traceback

from crawler_core.fetcher import fetch_by_chrome_debug


def fetch_rendered_html(url: str, timeout_seconds: int) -> dict[str, object]:
    """在独立解释器中通过 Chrome CDP 获取渲染后的完整 HTML。"""
    result = fetch_by_chrome_debug(url, timeout=timeout_seconds)
    return {
        "html": result.html,
        "final_url": result.final_url,
        "warnings": list(result.warnings),
    }


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Chrome CDP HTML 渲染助手")
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    return parser


def main() -> int:
    """解析参数、执行采集并以 JSON 输出结果。"""
    argument_parser = build_parser()
    arguments = argument_parser.parse_args()
    try:
        payload = fetch_rendered_html(
            url=arguments.url,
            timeout_seconds=arguments.timeout,
        )
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
