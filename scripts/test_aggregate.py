#!/usr/bin/env python3
"""Unit tests for report normalization and regression logic."""

import unittest

import aggregate


class AggregateTests(unittest.TestCase):
    def test_normalize_pipeline_report_canonicalizes_legacy_ops(self):
        report = {
            "datasets": {
                "wide": {
                    "operations": {
                        "deserializeXml": {
                            "iterations": 10,
                            "mean_ns": 100,
                            "stddev_ns": 10,
                        }
                    }
                }
            }
        }

        normalized, op_map = aggregate.normalize_pipeline_report(report)
        ops = normalized["datasets"]["wide"]["operations"]

        self.assertIn("deserialize_xml", ops)
        self.assertEqual(op_map["deserializeXml"], "deserialize_xml")
        self.assertEqual(ops["deserialize_xml"]["operation_id"], "deserialize_xml")
        self.assertEqual(ops["deserialize_xml"]["operation_track"], "xml")
        self.assertEqual(ops["deserialize_xml"]["sample_count"], 10)

    def test_compute_regressions_prefers_sample_count(self):
        current = {
            "id": "sdk-a",
            "pipeline": {
                "datasets": {
                    "wide": {
                        "operations": {
                            "deserialize": {
                                "mean_ns": 110,
                                "stddev_ns": 100,
                                "iterations": 10000,
                                "sample_count": 2,
                            }
                        }
                    }
                }
            },
        }
        previous = {
            "sdk-a": {
                "id": "sdk-a",
                "pipeline": {
                    "datasets": {
                        "wide": {
                            "operations": {
                                "deserialize": {
                                    "mean_ns": 100,
                                    "stddev_ns": 100,
                                    "iterations": 10000,
                                    "sample_count": 2,
                                }
                            }
                        }
                    }
                },
            }
        }

        regs = aggregate._compute_regressions(current, previous)
        # With small sample_count and high variance, change should not be significant.
        self.assertEqual(regs, [])

    def test_derive_capabilities_and_core_eligibility(self):
        report = {
            "datasets": {
                "wide": {"operations": {op: {} for op in aggregate.CORE_OPERATIONS}},
                "deep": {"operations": {op: {} for op in aggregate.CORE_OPERATIONS}},
                "mixed": {"operations": {op: {} for op in aggregate.CORE_OPERATIONS}},
                "val_regex": {"operations": {"validate": {}}},
                "wide_xml": {"operations": {"deserialize_xml": {}}},
                "aasx_small": {"operations": {"aasx_extract": {}}},
            }
        }
        caps, eligible = aggregate.derive_capabilities(report)

        self.assertTrue(eligible)
        self.assertTrue(caps["core"])
        self.assertTrue(caps["validation"])
        self.assertTrue(caps["xml"])
        self.assertTrue(caps["aasx"])


if __name__ == "__main__":
    unittest.main()
