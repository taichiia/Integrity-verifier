import csv
import json
import os
import tempfile

from verifier.report import (
    STATUS_LABELS,
    write_csv_report,
    write_json_report,
    write_txt_report,
)


SAMPLE_RESULTS = [
    {"path": "a.txt", "status": "pass", "expected": "abc", "actual": "abc"},
    {"path": "b.txt", "status": "fail", "expected": "abc", "actual": "xyz"},
    {"path": "c.txt", "status": "missing", "expected": "abc", "actual": ""},
    {"path": "extra.log", "status": "extra", "expected": "", "actual": ""},
]


def test_csv_report_includes_actual_hash_column():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "report.csv")
        write_csv_report(path, SAMPLE_RESULTS, "D:/release")
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

    assert rows[0] == ["状态", "文件路径", "期望哈希值", "实际哈希值"]
    assert rows[1] == ["pass", "a.txt", "abc", "abc"]
    assert rows[2] == ["fail", "b.txt", "abc", "xyz"]
    assert rows[3] == ["missing", "c.txt", "abc", ""]
    assert rows[4] == ["extra", "extra.log", "", ""]


def test_txt_report_uses_status_labels_and_summary():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "report.txt")
        write_txt_report(path, SAMPLE_RESULTS, "D:/release")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

    assert "目标路径: D:/release" in content
    assert "[通过] a.txt  (实际: abc)" in content
    assert "[失败] b.txt  (实际: xyz)" in content
    assert "[缺失] c.txt" in content
    assert "[多余] extra.log" in content
    assert "汇总: 1/4 通过, 3 项异常" in content


def test_empty_results_report_has_zero_summary():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "report.txt")
        write_txt_report(path, [], "")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

    assert "汇总: 0/0 通过, 0 项异常" in content


def test_status_labels_cover_all_statuses():
    assert STATUS_LABELS == {
        "pass": "通过", "fail": "失败", "missing": "缺失",
        "extra": "多余", "error": "错误",
    }


def test_json_report_has_machine_readable_summary():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "report.json")
        write_json_report(path, SAMPLE_RESULTS, "D:/release")
        with open(path, "r", encoding="utf-8") as f:
            report = json.load(f)

    assert report["target_path"] == "D:/release"
    assert [r["path"] for r in report["results"]] == [
        "a.txt", "b.txt", "c.txt", "extra.log",
    ]
    assert report["summary"] == {
        "pass": 1, "fail": 1, "missing": 1, "extra": 1, "error": 0, "total": 4,
    }
