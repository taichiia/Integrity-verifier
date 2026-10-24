import argparse
import json
import os
import sys
import time

EXIT_OK = 0
EXIT_VERIFY_FAILED = 1
EXIT_NO_DATA = 2
EXIT_BAD_TARGET = 3
EXIT_BAD_CHECKLIST = 4
EXIT_SELF_CHECK_FAILED = 5
EXIT_BAD_ALGORITHM = 6

_PROFILE = os.environ.get("FIT_STARTUP_PROFILE") == "1"


def _write(stream, text: str):
    """Print without assuming a console (frozen --noconsole builds lack one)."""
    if stream is None:
        return
    try:
        print(text, file=stream)
    except (OSError, ValueError):
        pass


def _profile(name: str, started: float):
    if _PROFILE:
        _write(sys.stderr, f"profile: {name}: "
                           f"{(time.perf_counter() - started) * 1000:.1f} ms")


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="File Integrity Verifier (CLI)")
    parser.add_argument("--target", required=True, help="待验证的目标目录")
    parser.add_argument("--algorithm", default=None,
                        help="哈希算法（默认使用内嵌配置中的算法）")
    parser.add_argument("--checklist", default=None,
                        help="选择内嵌校验清单（默认使用打包时活动清单）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出完整报告")
    parser.add_argument("--report", default=None,
                        help="将 JSON 报告写入指定文件（无控制台时仍可用）")
    args = parser.parse_args(argv)

    from shared.protection import verify_self_integrity
    self_ok, self_detail = verify_self_integrity()
    if not self_ok:
        _write(sys.stderr, f"错误: Verifier 自校验失败: {self_detail}")
        return EXIT_SELF_CHECK_FAILED

    if args.algorithm:
        import hashlib

        if args.algorithm.lower() not in hashlib.algorithms_available:
            _write(
                sys.stderr,
                f"错误: 不支持的哈希算法: {args.algorithm}\n"
                f"可用算法: {', '.join(sorted(hashlib.algorithms_available))}",
            )
            return EXIT_BAD_ALGORITHM

    from verifier.embedded import (
        EmbeddedConfigError, load_embedded_config, manifest_mismatch_message,
    )
    from verifier.report import STATUS_LABELS
    _profile("verification imports", started)

    try:
        config = load_embedded_config()
    except EmbeddedConfigError as e:
        _write(sys.stderr, f"{e.title}: {e.message}")
        return EXIT_NO_DATA

    checklists = config.get("checklists", {})
    if args.checklist:
        if args.checklist not in checklists:
            _write(
                sys.stderr,
                f"错误: 校验清单不存在: {args.checklist}\n"
                f"可用清单: {', '.join(checklists) or '(无)'}",
            )
            return EXIT_BAD_CHECKLIST
        config["checksum_entries"] = checklists[args.checklist]

    warning = manifest_mismatch_message(config)
    if warning:
        _write(sys.stderr, f"警告: {warning}")
    _profile("embedded load + self check", started)

    entries = config.get("checksum_entries", [])
    if not entries:
        _write(sys.stderr, "错误: 验证器不包含校验清单。")
        return EXIT_NO_DATA

    target = args.target
    if not os.path.isdir(target):
        _write(sys.stderr, f"错误: 目标目录不存在: {target}")
        return EXIT_BAD_TARGET

    algorithm = args.algorithm or config.get("algorithm", "sha256")

    exclude = []
    if getattr(sys, "frozen", False):
        exclude.append(sys.executable)

    from shared.verification import run_verification
    reports: list[dict] = []
    report = run_verification(
        entries, target, algorithm,
        exclude_paths=exclude,
        exclude_rules=config.get("exclude_rules"),
        ignored_paths=config.get("exclude_paths"),
    )
    _profile("target scan + hash", started)

    if args.report:
        try:
            with open(args.report, "w", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
        except OSError as e:
            _write(sys.stderr, f"错误: 无法写入报告文件: {e}")

    if args.json:
        _write(sys.stdout, json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for d in report.get("details", []):
            label = STATUS_LABELS.get(d["status"], d["status"])
            _write(sys.stdout, f"[{label}] {d['path']}")
        _write(
            sys.stdout,
            f"汇总: 通过 {report['passed']}/{report['total']} "
            f"失败 {report['failed']} 缺失 {report['missing']} "
            f"多余 {report.get('extra_count', 0)}",
        )

    # Extra files are a real mismatch: the target folder is supposed to match
    # the manifest exactly (ignored files are already filtered by FileRules).
    if (report["failed"] > 0 or report["missing"] > 0
            or report.get("extra_count", 0) > 0):
        return EXIT_VERIFY_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
