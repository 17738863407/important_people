from __future__ import annotations

from pathlib import Path
import sys

PAGE_RULE = {"rule_id": '4585'}


def parse_page(html, final_url, page_rule):
    """当前在线结构未完成核验，主动拒绝生成推测人物。"""
    raise RuntimeError('州长DOM容器为空；动态/queryList经HTTPS请求TLS握手失败，HTTP请求返回404，未完成当前完整领导数据结构核验')


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
