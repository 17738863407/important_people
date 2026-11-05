"""在线结构未核验，安全失败入口，等待网站恢复后重新适配。"""
from pathlib import Path
import sys

PAGE_RULE = {'rule_id': '4698', 'unverified_reason': '主表领导链接当前为县委领导栏目，与县人民政府目标机构不一致，需要人工确认正确领导入口', 'verification_note': '当前网页title及面包屑均为县委领导，拒绝混入县人民政府输出'}


def parse_page(html, final_url, page_rule):
    """拒绝在缺少当前在线证据时生成猜测人物结果。"""
    raise RuntimeError(page_rule["unverified_reason"])


def resolve_project_dir() -> Path:
    """从当前脚本向上寻找项目标记，兼容任意脚本层级。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
