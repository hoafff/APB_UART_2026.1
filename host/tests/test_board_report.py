import codecs
import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))
import board_report as report


PLANS = {
    "target": [
        dict(id="HW07", title="Echo 8N1", steps='Bật SW17, tắt local echo.\nGửi "55 AA 00 FF".',
             expected="RX 55 AA 00 FF", evidence="Lưu log TX, RX"),
        dict(id="HW08", title="Giữ RX", steps="Bật SW16, gửi 17 byte rồi hạ SW16",
             expected="LEDR1 sáng", evidence="Ảnh LED"),
    ],
    "pulp": [
        dict(id="HW07", title="Reset khi đang truyền", steps="Nhả KEY0 rồi gửi 5A với echo bật",
             expected="RX 5A", evidence="Log sau reset"),
    ],
}
BLANK = dict(status="NOT_RUN", observed="", evidence_path="", datetime_local="")


class BoardReportTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.sheet = self.folder / "Phiếu thử.csv"
        self.results = report.new_results(PLANS)

    def read_sheet(self):
        with self.sheet.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_load_utf8_next_to_module(self):
        source = self.folder / "board_plans.json"
        source.write_text(json.dumps(PLANS, ensure_ascii=False), encoding="utf-8")
        with patch.object(report, "__file__", str(self.folder / "board_report.py")):
            self.assertEqual(report.load_plans(), PLANS)

    def test_missing_malformed_and_invalid_plans(self):
        source = self.folder / "board_plans.json"
        echo = PLANS["target"][0]
        with patch.object(report, "__file__", str(self.folder / "board_report.py")):
            with self.assertRaises(FileNotFoundError):
                report.load_plans()
            source.write_text("{", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                report.load_plans()
            source.write_bytes(b'"\xff"')
            with self.assertRaises(UnicodeDecodeError):
                report.load_plans()
            for plans, message in (
                ({"target": []}, "pulp"),
                ({"target": [], "pulp": {}}, "pulp"),
                ({"target": [dict(echo, steps=["send"])], "pulp": []}, "steps"),
                ({"target": [echo, echo], "pulp": []}, "duplicate id"),
            ):
                with self.subTest(message=message, plans=plans):
                    source.write_text(json.dumps(plans), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        report.load_plans()

    def test_bundled_plan_and_export_counts(self):
        plans = report.load_plans()
        results = report.new_results(plans)
        for profile, count in (("target", 14), ("pulp", 8)):
            with self.subTest(profile=profile):
                cases = plans[profile]
                case_ids = [case["id"] for case in cases]
                self.assertEqual(len(case_ids), count)
                self.assertEqual(list(results[profile]), case_ids)
                report.save_sheet(self.sheet, profile, cases, results[profile], {})
                rows = self.read_sheet()
                self.assertEqual([row["test_id"] for row in rows], case_ids)
                for row in rows:
                    self.assertEqual(row["profile"], profile)
                    self.assertEqual({key: row[key] for key in BLANK}, BLANK)

    def test_results_are_independent_per_case_profile_and_session(self):
        for profile, cases in PLANS.items():
            self.assertEqual(self.results[profile], {case["id"]: BLANK for case in cases})
        self.results["target"]["HW07"].update(status="PASS", observed="RX 55 AA 00 FF")
        self.assertEqual(self.results["pulp"]["HW07"], BLANK)
        self.assertEqual(self.results["target"]["HW08"], BLANK)
        self.assertEqual(report.new_results(PLANS)["target"]["HW07"], BLANK)

    def test_export_preserves_header_order_multiline_hex_and_metadata(self):
        echo, hold = PLANS["target"]
        metadata = dict(operator='Nguyễn, "An"', board_id="DE2-115-02",
                        cp2102_id="COM10 / A07", sof_sha256="ab" * 32)
        recorded = dict(status="FAIL", observed='RX 55 AA 00 FE\r\nByte cuối là "FE", lệch một bit.',
                        evidence_path=r"C:\Kết quả\echo,01.log",
                        datetime_local="2026-11-19T09:12:30+07:00")
        self.results["target"]["HW07"].update(recorded)
        self.sheet.write_bytes(b"previous export")
        report.save_sheet(str(self.sheet), "target", [hold, echo], self.results["target"], metadata)

        header = (b"test_id,procedure,expected,status,datetime_local,operator,board_id,cp2102_id,"
                  b"sof_sha256,observed,evidence_path,profile,title,evidence_hint\r\n")
        self.assertTrue(self.sheet.read_bytes().startswith(codecs.BOM_UTF8 + header))
        hold_row, echo_row = self.read_sheet()
        for row, case, result in ((hold_row, hold, BLANK), (echo_row, echo, recorded)):
            self.assertEqual(row, {
                **metadata, **result, "test_id": case["id"], "profile": "target",
                "title": case["title"], "procedure": case["steps"],
                "expected": case["expected"], "evidence_hint": case["evidence"],
            })

    def test_simulated_match_leaves_board_status_unrun(self):
        note = "PTY MATCH, RX 5A"
        self.results["target"]["HW07"].update(status="PASS", evidence_path="target.log")
        self.results["pulp"]["HW07"]["observed"] = note
        report.save_sheet(self.sheet, "pulp", PLANS["pulp"], self.results["pulp"], {"operator": "An"})
        row, = self.read_sheet()
        self.assertEqual(row["profile"], "pulp")
        self.assertEqual(row["expected"], "RX 5A")
        self.assertEqual(row["observed"], note)
        self.assertEqual(row["status"], "NOT_RUN")
        self.assertEqual(row["operator"], "An")
        for field in ("board_id", "cp2102_id", "sof_sha256", "datetime_local", "evidence_path"):
            self.assertEqual(row[field], "")

    def test_encoding_failure_on_second_row_preserves_existing_sheet(self):
        self.sheet.write_bytes(b"operator's previous sheet")
        self.results["target"]["HW08"]["observed"] = "\ud800"
        with self.assertRaises(UnicodeEncodeError):
            report.save_sheet(self.sheet, "target", PLANS["target"], self.results["target"], {})
        self.assertEqual(self.sheet.read_bytes(), b"operator's previous sheet")
        self.assertEqual(list(self.folder.iterdir()), [self.sheet])

    def test_locked_destination_preserves_existing_sheet_and_allows_retry(self):
        self.sheet.write_bytes(b"operator's previous sheet")
        with patch.object(report.os, "replace", side_effect=PermissionError("workbook in use")):
            with self.assertRaises(PermissionError):
                report.save_sheet(self.sheet, "pulp", PLANS["pulp"], self.results["pulp"], {})
        self.assertEqual(self.sheet.read_bytes(), b"operator's previous sheet")
        self.assertEqual(list(self.folder.iterdir()), [self.sheet])
        report.save_sheet(self.sheet, "pulp", PLANS["pulp"], self.results["pulp"], {})
        self.assertEqual(self.read_sheet()[0]["status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
