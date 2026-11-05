from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path


MARKERS = (
    "llm_vision",
    "大模型视觉",
    "图片视觉解析",
    "codex_conversation",
    "需要大模型视觉解析",
)


def is_candidate(path: Path) -> bool:
    """判断输出 TXT 是否需要当前对话视觉处理。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return any(marker in text for marker in MARKERS)


def extract_rule_id(path: Path) -> str:
    """只接受现行项目契约的四位脚本编号，旧文件不猜测映射。"""
    prefix = path.name.split("_", 1)[0]
    return prefix if re.fullmatch(r"\d{4}", prefix) else ""


def main(output_argument: str, external_output: str | None) -> None:
    """从当前项目解析路径，只读扫描失败结果并保留全部同编号候选。"""
    project_dir = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(project_dir))
    from crawler_core.paths import resolve_project_path

    output_dir = (
        Path(external_output).expanduser().resolve()
        if external_output
        else resolve_project_path(output_argument, anchor=__file__, must_exist=True)
    )
    if not output_dir.is_dir():
        raise NotADirectoryError(f"输出目录不存在：{output_dir}")
    script_dir = resolve_project_path("important_people/site_adapters", anchor=__file__, must_exist=True)
    log_dir = resolve_project_path("important_people/workspace/log", anchor=__file__)
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / "scan_llm_vision_outputs.log", encoding="utf-8")],
    )
    scripts_by_id: dict[str, list[Path]] = {}
    for script_path in sorted(script_dir.rglob("*.py")):
        rule_id = extract_rule_id(script_path)
        if rule_id:
            scripts_by_id.setdefault(rule_id, []).append(script_path)
    print("输出文件\t规则编号\t对应脚本\t候选脚本数")
    candidate_count = 0
    for txt_path in sorted(output_dir.rglob("*.txt")):
        if not is_candidate(txt_path):
            continue
        candidate_count += 1
        rule_id = extract_rule_id(txt_path)
        script_matches = scripts_by_id.get(rule_id, []) if rule_id else []
        script_paths = " || ".join(str(path) for path in script_matches)
        print(f"{txt_path}\t{rule_id}\t{script_paths}\t{len(script_matches)}")
        if len(script_matches) != 1:
            logging.warning("候选需人工消歧：%s；规则编号=%s；脚本数=%s", txt_path, rule_id, len(script_matches))
    logging.info("只读扫描完成：输出目录=%s；待处理文件=%s", output_dir, candidate_count)


if __name__ == "__main__":
    output_argument_value = sys.argv[1] if len(sys.argv) > 1 else "important_people/outputs"
    external_output_value = os.environ.get("IMPORTANT_PEOPLE_VISION_OUTPUT_DIR")
    main(output_argument_value, external_output_value)
