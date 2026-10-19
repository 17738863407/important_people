from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path


@dataclass
class Issue:
    path: Path
    line_number: int
    url_value: str
    has_detail_url: bool
    context: str
    risk_level: str
    reason: str


DETAIL_HINTS = (
    "detail",
    "href",
    "link",
    "profile",
    "person_url",
    "item_url",
    "leader_url",
)


def node_to_text(node: ast.AST) -> str:
    """尽量把 AST 节点还原为可读表达式。"""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def const_key(node: ast.AST) -> str:
    """读取字典键名。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def looks_like_detail_value(expression_text: str) -> bool:
    """判断 url 字段值是否疑似详情页变量。"""
    lower_text = expression_text.lower()
    return any(hint in lower_text for hint in DETAIL_HINTS)


def inspect_dict_node(path: Path, node: ast.Dict) -> Issue | None:
    """检查单个字典是否存在 url/detail_url 字段错位风险。"""
    keys = [const_key(key) if key is not None else "" for key in node.keys]
    if "url" not in keys:
        return None
    context = "page_rule" if "rule_id" in keys and "organization" in keys else "record"
    url_index = keys.index("url")
    url_value_node = node.values[url_index]
    url_value = node_to_text(url_value_node)
    has_detail_url = "detail_url" in keys
    if has_detail_url or context == "page_rule":
        return None
    if looks_like_detail_value(url_value):
        return Issue(
            path=path,
            line_number=getattr(node, "lineno", 0),
            url_value=url_value,
            has_detail_url=has_detail_url,
            context=context,
            risk_level="high",
            reason='字典中 "url" 字段疑似写入详情页变量，且缺少 "detail_url" 字段',
        )
    return None


def inspect_script(path: Path) -> list[Issue]:
    """静态检查单个脚本。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            issue = inspect_dict_node(path, node)
            if issue is not None:
                issues.append(issue)
    return issues


def write_report(report_path: Path, issues: list[Issue], scanned_count: int) -> None:
    """写出检查报告。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as file:
        file.write("脚本 url 字段误写详情页风险检查报告\n")
        file.write(f"扫描脚本数\t{scanned_count}\n")
        file.write(f"风险项数\t{len(issues)}\n")
        file.write("风险等级\t上下文\t文件\t行号\turl字段表达式\t是否已有detail_url\t原因\n")
        for issue in issues:
            file.write(
                f"{issue.risk_level}\t{issue.context}\t{issue.path}\t{issue.line_number}\t{issue.url_value}\t"
                f"{issue.has_detail_url}\t{issue.reason}\n"
            )


def main(project_dir: Path) -> None:
    """统一入口。"""
    adapters_dir = project_dir / "site_adapters"
    report_path = project_dir / "workspace" / "reports" / "脚本url字段误写详情页风险检查报告.txt"
    scripts = sorted(path for path in adapters_dir.rglob("*.py") if path.is_file())
    issues: list[Issue] = []
    for script_path in scripts:
        issues.extend(inspect_script(script_path))
    write_report(report_path, issues, len(scripts))

    print(f"REPORT={report_path}")
    print(f"SCANNED={len(scripts)}")
    print(f"ISSUES={len(issues)}")
    for issue in issues[:30]:
        print(f"{issue.risk_level}\t{issue.context}\t{issue.path}\tline={issue.line_number}\turl={issue.url_value}")


if __name__ == "__main__":
    project_dir_value = resolve_project_path("important_people", anchor=__file__)
    main(project_dir=project_dir_value)
