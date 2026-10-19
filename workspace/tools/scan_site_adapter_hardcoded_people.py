from __future__ import annotations

import ast
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path


DUTY_KEYWORDS = (
    "书记",
    "主任",
    "副主任",
    "部长",
    "副部长",
    "局长",
    "副局长",
    "署长",
    "副署长",
    "会长",
    "副会长",
    "主席",
    "副主席",
    "秘书长",
    "副秘书长",
    "委员",
    "党组",
    "党委",
    "纪委",
    "纪检",
    "巡视员",
    "调研员",
    "总工程师",
    "总经济师",
    "总会计师",
    "总规划师",
    "总监",
    "监管总监",
    "董事长",
    "总经理",
    "副总经理",
    "院长",
    "副院长",
    "校长",
    "副校长",
    "站长",
    "副站长",
    "厅长",
    "副厅长",
    "处长",
    "副处长",
    "一级",
    "二级",
    "三级",
    "四级",
    "巡视专员",
    "政治部主任",
    "督察专员",
)
NON_PERSON_WORDS = (
    "姓名",
    "职务",
    "领导",
    "机构",
    "网址",
    "详情",
    "证据",
    "解析",
    "选择",
    "负责人",
    "局领导",
    "党组成员",
    "主任",
    "副主任",
    "局长",
    "副局长",
    "部长",
    "副部长",
    "党委",
    "党组",
    "政府",
    "页面",
    "列表",
    "官网",
)
URL_RE = re.compile(r"https?://[^'\"\s)\],}]+")
REL_DETAIL_RE = re.compile(r"(^|/|\.\./|\./)[^'\"\s<>]*(?:\.s?html|\.htm|\.jhtml|\.php)(?:$|[?#])", re.I)
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def is_probable_name(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) > 12:
        return False
    if not CHINESE_RE.search(text):
        return False
    if any(word == text or word in text for word in NON_PERSON_WORDS):
        return False
    cleaned = re.sub(r"[·.．•\s\u3000-]", "", text)
    if not (2 <= len(cleaned) <= 8):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fffA-Za-z]+", cleaned))


def looks_like_duty(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) < 2 or len(text) > 120:
        return False
    return any(keyword in text for keyword in DUTY_KEYWORDS)


def looks_like_detail_literal(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if text.lower() in {".html", ".htm", ".shtml", ".jhtml", ".php"}:
        return False
    if "127.0.0.1" in text or "localhost" in text.lower():
        return False
    if URL_RE.search(text):
        return True
    if REL_DETAIL_RE.search(text) and not any(token in text for token in ("(?", "<", ">", "\\", "*", "[", "]")):
        return True
    return False


def one_line(source: str, lineno: int) -> str:
    lines = source.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:260]
    return ""


def span_contains(spans: list[tuple[int, int]], lineno: int) -> bool:
    return any(start <= lineno <= end for start, end in spans)


def const_value(node: ast.AST | None) -> object:
    return node.value if isinstance(node, ast.Constant) else None


def target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(target_names(elt))
        return names
    return []


class Analyzer(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.page_rule_spans: list[tuple[int, int]] = []
        self.person_entries: list[dict[str, object]] = []
        self.detail_entries: list[dict[str, object]] = []
        self.assignment_stack: list[str] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        names: list[str] = []
        for target in node.targets:
            names.extend(target_names(target))
        if "PAGE_RULE" in names:
            self.page_rule_spans.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
        self.assignment_stack.append(",".join(names))
        self.generic_visit(node)
        self.assignment_stack.pop()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        names = target_names(node.target)
        self.assignment_stack.append(",".join(names))
        self.generic_visit(node)
        self.assignment_stack.pop()

    def visit_Tuple(self, node: ast.Tuple) -> None:
        values = [const_value(elt) for elt in node.elts]
        if len(values) >= 2 and is_probable_name(values[0]) and looks_like_duty(values[1]):
            detail_values = [v for v in values[2:] if looks_like_detail_literal(v)]
            self.person_entries.append(
                {
                    "line": node.lineno,
                    "kind": "tuple_name_duty_url" if detail_values else "tuple_name_duty",
                    "assignment": self.assignment_stack[-1] if self.assignment_stack else "",
                    "name": values[0],
                    "duty": values[1],
                    "detail_url": detail_values[0] if detail_values else "",
                    "snippet": one_line(self.source, node.lineno),
                }
            )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        items: dict[str, object] = {}
        for key, value in zip(node.keys, node.values):
            key_value = const_value(key)
            value_value = const_value(value)
            if isinstance(key_value, str):
                items[key_value] = value_value
        name = items.get("name") or items.get("姓名")
        duty = items.get("duty") or items.get("职务")
        detail = items.get("detail_url") or items.get("详情页") or items.get("url")
        if is_probable_name(name) and looks_like_duty(duty):
            self.person_entries.append(
                {
                    "line": node.lineno,
                    "kind": "dict_name_duty_url" if looks_like_detail_literal(detail) else "dict_name_duty",
                    "assignment": self.assignment_stack[-1] if self.assignment_stack else "",
                    "name": name,
                    "duty": duty,
                    "detail_url": detail if looks_like_detail_literal(detail) else "",
                    "snippet": one_line(self.source, node.lineno),
                }
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        value = node.value
        if looks_like_detail_literal(value) and not span_contains(self.page_rule_spans, node.lineno):
            self.detail_entries.append(
                {
                    "line": node.lineno,
                    "assignment": self.assignment_stack[-1] if self.assignment_stack else "",
                    "value": str(value).strip(),
                    "snippet": one_line(self.source, node.lineno),
                }
            )
        self.generic_visit(node)


def analyze_file(path: Path) -> tuple[Analyzer, str]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=str(path))
    analyzer = Analyzer(source)
    analyzer.visit(tree)
    analyzer.detail_entries = [
        entry for entry in analyzer.detail_entries if not span_contains(analyzer.page_rule_spans, int(entry["line"]))
    ]
    return analyzer, source


def main(project_dir: Path, adapter_dir: Path, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = log_dir / f"site_adapters_hardcoded_person_detail_report_{run_ts}.txt"
    detail_path = log_dir / f"site_adapters_hardcoded_person_detail_details_{run_ts}.txt"

    records: list[dict[str, object]] = []
    errors: list[tuple[Path, str]] = []
    all_files = sorted(adapter_dir.rglob("*.py"))
    for path in all_files:
        try:
            analyzer, _source = analyze_file(path)
        except Exception as error:
            errors.append((path, str(error)))
            continue

        detail_entries = analyzer.detail_entries
        person_entries = analyzer.person_entries
        person_with_url = [entry for entry in person_entries if entry.get("detail_url")]
        flags: list[str] = []
        if detail_entries:
            flags.append("硬编码URL/详情页候选")
        if person_entries:
            flags.append("硬编码人物职务")
        if person_with_url:
            flags.append("姓名职务详情页三元组")
        if flags:
            records.append(
                {
                    "path": path,
                    "relpath": str(path.relative_to(project_dir)),
                    "folder": str(path.parent.relative_to(adapter_dir)),
                    "flags": "、".join(flags),
                    "detail_entries": detail_entries,
                    "person_entries": person_entries,
                    "detail_count": len(detail_entries),
                    "person_count": len(person_entries),
                    "person_url_count": len(person_with_url),
                }
            )

    counter_by_flags = Counter(str(record["flags"]) for record in records)
    counter_by_folder = Counter(str(record["folder"]) for record in records)
    summary_lines: list[str] = []
    summary_lines.append("site_adapters 硬编码详情页链接与人物职务信息扫描报告")
    summary_lines.append(f"生成时间\t{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_lines.append(f"扫描目录\t{adapter_dir}")
    summary_lines.append(f"脚本总数\t{len(all_files)}")
    summary_lines.append(f"可疑脚本数\t{len(records)}")
    summary_lines.append(f"硬编码URL/详情页候选脚本数\t{sum(1 for record in records if record['detail_count'])}")
    summary_lines.append(f"硬编码人物职务脚本数\t{sum(1 for record in records if record['person_count'])}")
    summary_lines.append(f"姓名+职务+详情页三元组脚本数\t{sum(1 for record in records if record['person_url_count'])}")
    summary_lines.append(f"解析失败脚本数\t{len(errors)}")
    summary_lines.append("")
    summary_lines.append("判定口径")
    summary_lines.append("1. PAGE_RULE 内的入口网址视为正常配置，不计入硬编码详情页链接。")
    summary_lines.append("2. 代码中出现 http(s) URL 或 .html/.htm/.shtml/.jhtml/.php 字面量，且不在 PAGE_RULE 中，计入硬编码URL/详情页候选；localhost 与单独后缀字符串已排除。")
    summary_lines.append("3. 代码中出现形如 (姓名, 职务) 或 (姓名, 职务, 详情页URL) 的字面量元组，或 dict 直接写 name/duty，计入硬编码人物职务候选。")
    summary_lines.append("4. 报告为静态扫描结果，个别脚本可能属于图片页人工校验、反爬兜底或旧模板遗留，需要后续逐个确认。")
    summary_lines.append("")
    summary_lines.append("按类型统计")
    for key, count in counter_by_flags.most_common():
        summary_lines.append(f"{key}\t{count}")
    summary_lines.append("")
    summary_lines.append("按目录统计")
    for key, count in counter_by_folder.most_common():
        summary_lines.append(f"{key}\t{count}")
    summary_lines.append("")
    summary_lines.append("可疑脚本清单")
    summary_lines.append("相对路径\t问题类型\t硬编码URL/详情页候选数\t硬编码人物职务条数\t姓名职务详情页三元组条数\t人物职务示例\tURL/详情页候选示例")
    for record in records:
        person_examples = record["person_entries"][:5]
        detail_examples = record["detail_entries"][:5]
        person_example_text = "；".join(
            f"L{entry['line']} {entry.get('name', '')}|{entry.get('duty', '')}|{entry.get('detail_url', '')}"
            for entry in person_examples
        )
        detail_example_text = "；".join(f"L{entry['line']} {entry.get('value', '')}" for entry in detail_examples)
        summary_lines.append(
            f"{record['relpath']}\t{record['flags']}\t{record['detail_count']}\t{record['person_count']}\t"
            f"{record['person_url_count']}\t{person_example_text}\t{detail_example_text}"
        )
    if errors:
        summary_lines.append("")
        summary_lines.append("解析失败脚本")
        for path, error in errors[:200]:
            summary_lines.append(f"{path.relative_to(project_dir)}\t{error}")
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    detail_lines = ["相对路径\t类别\t行号\t变量/上下文\t姓名\t职务\t详情页链接或URL\t代码片段"]
    for record in records:
        for entry in record["person_entries"]:
            snippet = str(entry.get("snippet", "")).replace("\t", " ")
            detail_lines.append(
                f"{record['relpath']}\t硬编码人物职务\t{entry['line']}\t{entry.get('assignment', '')}\t"
                f"{entry.get('name', '')}\t{entry.get('duty', '')}\t{entry.get('detail_url', '')}\t{snippet}"
            )
        for entry in record["detail_entries"]:
            snippet = str(entry.get("snippet", "")).replace("\t", " ")
            detail_lines.append(
                f"{record['relpath']}\t硬编码URL/详情页候选\t{entry['line']}\t{entry.get('assignment', '')}\t\t\t"
                f"{entry.get('value', '')}\t{snippet}"
            )
    detail_path.write_text("\n".join(detail_lines) + "\n", encoding="utf-8")

    print(f"SUMMARY={summary_path}")
    print(f"DETAIL={detail_path}")
    print(f"PY_FILES={len(all_files)}")
    print(f"SUSPECT_FILES={len(records)}")
    print(f"DETAIL_URL_CANDIDATE_FILES={sum(1 for record in records if record['detail_count'])}")
    print(f"PERSON_DUTY_FILES={sum(1 for record in records if record['person_count'])}")
    print(f"PERSON_DUTY_URL_FILES={sum(1 for record in records if record['person_url_count'])}")
    print(f"PARSE_ERRORS={len(errors)}")


if __name__ == "__main__":
    project_dir_value = resolve_project_path("important_people", anchor=__file__)
    adapter_dir_value = project_dir_value / "site_adapters"
    log_dir_value = project_dir_value / "workspace" / "log"
    main(project_dir_value, adapter_dir_value, log_dir_value)
