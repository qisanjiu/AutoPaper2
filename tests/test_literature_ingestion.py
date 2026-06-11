from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from spiral.literature_ingestion import (
    _query_variants,
    normalize_source_log_data,
    prepare_source_log,
    save_browser_session_state,
    search_literature,
)
from utils.source_log_validator import validate


class TestLiteratureIngestionHelper(unittest.TestCase):
    def test_prepare_source_log_adds_contract_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_log = root / "knowledge" / "M1" / "M1_source_log.yaml"
            source_log.parent.mkdir(parents=True)
            data = {
                "search_provenance": _search_provenance(["s1", "s2", "s3", "s4", "s5"]),
                "sources": [_source(i) for i in range(1, 6)],
                "gap_evidence_map": _gap_map(),
            }
            source_log.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

            report = prepare_source_log(source_log, project_root=root)

            self.assertEqual(report.sources_seen, 5)
            self.assertEqual(report.discovery_added, 5)
            self.assertGreaterEqual(report.artifacts_added, 5)
            self.assertEqual(report.parse_profiles_added, 5)

            updated = yaml.safe_load(source_log.read_text(encoding="utf-8"))
            first = updated["sources"][0]
            self.assertIn("discovery_records", first)
            self.assertEqual(first["artifacts"][0]["artifact_type"], "pdf")
            self.assertEqual(first["parse_profile"]["parse_status"], "partial")
            self.assertIn("M3", first["parse_profile"]["downstream_signals"])

            ok, messages = validate(root, "M1")
            self.assertTrue(ok, messages)

    def test_failed_artifact_gets_recovery_actions(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Broken PDF Paper",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "venue": "Venue",
                    "year": 2024,
                    "url": "https://example.com/paper",
                    "artifacts": [
                        {
                            "artifact_type": "pdf",
                            "uri": "https://example.com/missing.pdf",
                            "status": "failed",
                        }
                    ],
                    **_deep_fields(1),
                }
            ]
        }

        report = normalize_source_log_data(data)

        self.assertEqual(report.sources_seen, 1)
        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(artifact["status"], "failed")
        self.assertTrue(artifact["failure_reason"])
        self.assertTrue(artifact["recovery_actions"])

    def test_source_without_url_uses_metadata_artifact(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Metadata Only Paper",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "venue": "Venue",
                    "year": 2024,
                    **_deep_fields(1),
                }
            ]
        }

        normalize_source_log_data(data)

        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(artifact["artifact_type"], "abstract")
        self.assertEqual(artifact["status"], "available")
        self.assertEqual(data["sources"][0]["parse_profile"]["fulltext_status"], "metadata_only")

    def test_unknown_artifact_gets_explicit_pending_reason(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Publisher Page Paper",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "venue": "IEEE Transactions",
                    "year": 2024,
                    "url": "https://doi.org/10.1109/example",
                    "artifacts": [
                        {
                            "artifact_type": "html",
                            "uri": "https://doi.org/10.1109/example",
                            "status": "unknown",
                        }
                    ],
                    **_deep_fields(1),
                }
            ]
        }

        normalize_source_log_data(data)

        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(artifact["status"], "unknown")
        self.assertTrue(artifact["failure_reason"])
        self.assertIn("fallback", " ".join(artifact["recovery_actions"]))

    def test_abstract_can_supply_bounded_downstream_signals(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Abstract Rich Paper",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "venue": "Venue",
                    "year": 2024,
                    "url": "https://example.com/paper",
                    "abstract": (
                        "We propose a joint coding modulation framework for image "
                        "semantic communication. Experiments validate the method over "
                        "different channel SNR settings and modulation orders. Results "
                        "demonstrate superior performance and robust behavior."
                    ),
                }
            ]
        }

        normalize_source_log_data(data)

        profile = data["sources"][0]["parse_profile"]
        self.assertTrue(profile["downstream_signals"]["M2"]["method_reference"])
        self.assertTrue(profile["downstream_signals"]["M3"]["experiment_protocol"])
        self.assertTrue(profile["downstream_signals"]["M4"]["analysis_patterns"])
        self.assertNotIn("method", profile["missing_fields"])

    def test_search_records_publisher_coverage(self) -> None:
        found = [
            {
                "id": "s1",
                "title": "IEEE Semantic Communication Paper",
                "venue": "IEEE Transactions on Communications",
                "publisher": "IEEE",
                "identifiers": {"doi": "10.1109/example"},
            },
            {
                "id": "s2",
                "title": "Elsevier Image Communication Paper",
                "venue": "Digital Communications and Networks",
                "publisher": "Elsevier",
                "identifiers": {"doi": "10.1016/example"},
            },
        ]
        with patch("spiral.literature_ingestion._search_openalex", return_value=found):
            data = search_literature("semantic communication", limit=2, surfaces=["openalex"])

        coverage = data["search_provenance"]["publisher_coverage"]
        self.assertTrue(coverage["IEEE"]["covered"])
        self.assertTrue(coverage["Elsevier/ScienceDirect"]["covered"])

    def test_search_filters_sources_missing_query_specific_terms(self) -> None:
        found = [
            {
                "id": "relevant",
                "title": "Image Semantic Communication with Digital Modulation",
                "abstract": "An image semantic communication system with modulation.",
            },
            {
                "id": "offtopic",
                "title": "A Theory of Semantic Communication",
                "abstract": "General semantic communication theory.",
            },
        ]
        with patch("spiral.literature_ingestion._search_openalex", return_value=found):
            data = search_literature(
                "image semantic communication digital modulation",
                limit=2,
                surfaces=["openalex"],
            )

        self.assertEqual([src["id"] for src in data["sources"]], ["relevant"])
        self.assertEqual(
            data["search_provenance"]["screening_exclusions"][0]["source_id"],
            "offtopic",
        )

    def test_query_variants_expand_semantic_modulation_topic(self) -> None:
        variants = _query_variants("数字图像语义通信，数字调制 image semantic communication digital modulation")

        self.assertIn("image semantic communication digital modulation", variants)
        self.assertTrue(any("joint coding modulation" in variant for variant in variants))
        self.assertLessEqual(len(variants), 8)

    def test_query_variants_prefer_english_for_chinese_topic(self) -> None:
        variants = _query_variants("数字图像语义通信，数字调制")

        self.assertEqual(variants[0], "image semantic communication digital modulation")
        self.assertIn("数字图像语义通信，数字调制", variants)

    def test_credential_gated_surface_records_failure_round(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            data = search_literature(
                "image semantic communication digital modulation",
                limit=2,
                surfaces=["ieee"],
            )

        self.assertEqual(data["sources"], [])
        failure_round = data["search_provenance"]["rounds"][0]
        self.assertIn("IEEE Xplore connector requires", failure_round["failure_reason"])
        self.assertIn("ieee", data["search_provenance"]["databases"])

    def test_wos_surface_without_key_records_actionable_failure(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            data = search_literature(
                "image semantic communication digital modulation",
                limit=1,
                surfaces=["wos"],
            )

        self.assertEqual(data["sources"], [])
        failure_reason = data["search_provenance"]["rounds"][0]["failure_reason"]
        self.assertIn("Web of Science connector requires", failure_reason)
        self.assertNotIn("NotImplemented", failure_reason)

    def test_wos_surface_parses_starter_documents(self) -> None:
        payload = {
            "hits": [
                {
                    "uid": "WOS:123",
                    "title": "Image Semantic Communication with Digital Modulation",
                    "source": {"sourceTitle": "IEEE Transactions", "publishYear": 2025},
                    "identifiers": {"doi": "10.1109/example"},
                    "names": {"authors": [{"displayName": "A. Author"}]},
                    "links": {"record": "https://www.webofscience.com/wos/woscc/full-record/WOS:123"},
                    "citations": [{"db": "WOS", "count": 7}],
                    "abstract": "A semantic communication method for image transmission and digital modulation.",
                }
            ]
        }
        with patch.dict("os.environ", {"WOS_API_KEY": "dummy"}, clear=True), patch(
            "spiral.literature_ingestion._http_json", return_value=payload
        ) as mocked_json:
            data = search_literature(
                "image semantic communication digital modulation",
                limit=1,
                surfaces=["wos"],
            )

        self.assertEqual(len(data["sources"]), 1)
        source = data["sources"][0]
        self.assertEqual(source["identifiers"]["wos_uid"], "WOS:123")
        self.assertEqual(source["citation_count"], 7)
        self.assertIn("X-ApiKey", mocked_json.call_args.kwargs["headers"])

    def test_acm_surface_uses_crossref_tdm_links(self) -> None:
        payload = {
            "message": {
                "items": [
                    {
                        "title": ["Task-Driven Semantic Image Communication over Underwater Acoustic Channels"],
                        "DOI": "10.1145/3784941.3785435",
                        "publisher": "ACM",
                        "issued": {"date-parts": [[2025]]},
                        "container-title": ["ACM Conference"],
                        "author": [{"given": "A.", "family": "Author"}],
                        "URL": "https://doi.org/10.1145/3784941.3785435",
                        "abstract": "This image semantic communication work studies digital modulation over channels.",
                        "link": [
                            {
                                "URL": "https://dl.acm.org/doi/pdf/10.1145/3784941.3785435",
                                "content-type": "application/pdf",
                                "intended-application": "text-mining",
                            }
                        ],
                    }
                ]
            }
        }
        with patch("spiral.literature_ingestion._http_json", return_value=payload):
            data = search_literature(
                "image semantic communication digital modulation",
                limit=1,
                surfaces=["acm"],
            )

        self.assertEqual(len(data["sources"]), 1)
        self.assertEqual(data["sources"][0]["publisher"], "ACM")
        self.assertEqual(data["sources"][0]["artifacts"][0]["artifact_type"], "pdf")
        self.assertIn("dl.acm.org/doi/pdf", data["sources"][0]["artifacts"][0]["uri"])

    def test_wiley_surface_uses_crossref_tdm_links_with_auth_metadata(self) -> None:
        payload = {
            "message": {
                "items": [
                    {
                        "title": ["Optimization of Image Transmission in Semantic Communication Networks"],
                        "DOI": "10.1002/example",
                        "publisher": "Wiley",
                        "issued": {"date-parts": [[2024]]},
                        "container-title": ["Wiley Book"],
                        "author": [{"given": "A.", "family": "Author"}],
                        "URL": "https://doi.org/10.1002/example",
                        "abstract": "Image semantic communication with digital modulation and channel evaluation.",
                        "link": [
                            {
                                "URL": "https://api.wiley.com/onlinelibrary/tdm/v1/articles/10.1002%2Fexample",
                                "content-type": "application/pdf",
                                "intended-application": "text-mining",
                            }
                        ],
                    }
                ]
            }
        }
        with patch("spiral.literature_ingestion._http_json", return_value=payload):
            data = search_literature(
                "image semantic communication digital modulation",
                limit=1,
                surfaces=["wiley"],
            )

        self.assertEqual(len(data["sources"]), 1)
        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(artifact["artifact_type"], "pdf")
        self.assertEqual(artifact["auth_env"], "WILEY_TDM_TOKEN")
        self.assertIn("Wiley", artifact["auth_header"])

    def test_fetch_fulltext_records_publisher_credential_blocker(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Image Semantic Communication with Digital Modulation",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "venue": "IEEE Transactions on Communications",
                    "publisher": "IEEE",
                    "year": 2024,
                    "url": "https://doi.org/10.1109/example",
                    "identifiers": {"doi": "10.1109/example"},
                    "abstract": (
                        "We propose an image semantic communication method with "
                        "digital modulation and evaluate it over channel settings."
                    ),
                }
            ]
        }

        with patch.dict("os.environ", {}, clear=True), patch(
            "spiral.literature_ingestion._unpaywall_artifacts", return_value=[]
        ):
            report = normalize_source_log_data(data, fetch_fulltext=True)

        self.assertEqual(report.credential_blocked, 1)
        artifacts = data["sources"][0]["artifacts"]
        blockers = [artifact for artifact in artifacts if artifact["uri"] == "credential:IEEE"]
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["status"], "skipped")
        self.assertTrue(blockers[0]["failure_reason"])

    def test_skip_crossref_fulltext_avoids_per_doi_lookup(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Elsevier Image Semantic Communication",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "Elsevier",
                    "venue": "Physical Communication",
                    "year": 2025,
                    "url": "https://doi.org/10.1016/example",
                    "identifiers": {"doi": "10.1016/example"},
                    "abstract": "Image semantic communication with digital modulation.",
                }
            ]
        }

        with patch("spiral.literature_ingestion._crossref_doi_artifacts") as mocked_crossref:
            normalize_source_log_data(
                data,
                fetch_fulltext=True,
                skip_unpaywall=True,
                skip_crossref_fulltext=True,
            )

        mocked_crossref.assert_not_called()
        artifact_uris = [artifact["uri"] for artifact in data["sources"][0]["artifacts"]]
        self.assertTrue(any("api.elsevier.com/content/article/doi" in uri for uri in artifact_uris))

    def test_publisher_pdf_is_deferred_in_bulk_without_credentials(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "ACM Image Semantic Communication",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "ACM",
                    "venue": "ACM Conference",
                    "year": 2025,
                    "url": "https://doi.org/10.1145/example",
                    "artifacts": [
                        {
                            "artifact_type": "pdf",
                            "uri": "https://dl.acm.org/doi/pdf/10.1145/example",
                            "status": "unknown",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            report = normalize_source_log_data(
                data,
                project_root=Path(tmp),
                fetch_fulltext=True,
                download_pdfs=True,
                skip_unpaywall=True,
                skip_crossref_fulltext=True,
            )

        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(report.pdf_download_attempted, 0)
        self.assertEqual(artifact["status"], "pending")
        self.assertIn("credential-gated", artifact["failure_reason"])

    def test_browser_session_downloads_credential_gated_pdf(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "IEEE Image Semantic Communication",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "IEEE",
                    "venue": "IEEE Transactions",
                    "year": 2025,
                    "url": "https://doi.org/10.1109/example",
                    "artifacts": [
                        {
                            "artifact_type": "pdf",
                            "uri": "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=123456",
                            "status": "unknown",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "browser_state.json"
            state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            with patch(
                "spiral.literature_ingestion._fetch_with_browser_session",
                return_value=(b"%PDF-1.7\nbrowser licensed pdf", "pdf", "https://ieeexplore.ieee.org/document/123456"),
            ):
                report = normalize_source_log_data(
                    data,
                    project_root=root,
                    download_pdfs=True,
                    browser_downloads=True,
                    browser_session_state=state,
                )

            artifact = data["sources"][0]["artifacts"][0]
            local_path = root / artifact["local_path"]
            self.assertEqual(report.browser_download_attempted, 1)
            self.assertEqual(report.browser_downloaded, 1)
            self.assertEqual(report.pdf_download_attempted, 0)
            self.assertEqual(artifact["status"], "available")
            self.assertEqual(artifact["artifact_type"], "pdf")
            self.assertTrue(artifact["sha256"])
            self.assertIn("authorized browser session", artifact["notes"])
            self.assertTrue(local_path.exists())

    def test_structured_xml_is_preferred_over_pdf_and_parsed(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Wiley Structured Full Text",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "Wiley",
                    "venue": "Wiley Journal",
                    "year": 2025,
                    "url": "https://doi.org/10.1002/example",
                    "artifacts": [
                        {
                            "artifact_type": "pdf",
                            "uri": "https://onlinelibrary.wiley.com/doi/pdf/10.1002/example",
                            "status": "unknown",
                        },
                        {
                            "artifact_type": "xml",
                            "uri": "https://onlinelibrary.wiley.com/doi/full-xml/10.1002/example",
                            "status": "unknown",
                            "notes": "Crossref publisher full-text link; intended=text-mining",
                        },
                    ],
                }
            ]
        }
        xml_bytes = b"""
        <article>
          <abstract><p>Image semantic communication over channels.</p></abstract>
          <sec><title>Method</title><p>We propose a joint coding modulation method.</p></sec>
          <sec><title>Experimental Setup</title><p>Experiments use datasets, metrics, baselines, and channel splits.</p></sec>
          <sec><title>Results</title><p>Results improve semantic accuracy and reconstruction quality.</p></sec>
          <sec><title>Analysis</title><p>Ablation and robustness analysis inspect channel noise.</p></sec>
        </article>
        """ + b" semantic communication channel evaluation" * 200

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "browser_state.json"
            state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            with patch(
                "spiral.literature_ingestion._fetch_with_browser_session",
                return_value=(xml_bytes, "xml", "https://onlinelibrary.wiley.com/doi/full-xml/10.1002/example"),
            ) as fetch:
                report = normalize_source_log_data(
                    data,
                    project_root=root,
                    fetch_fulltext=True,
                    download_pdfs=True,
                    browser_downloads=True,
                    browser_session_state=state,
                    parse_local_pdfs=True,
                    skip_unpaywall=True,
                    skip_crossref_fulltext=True,
                )

            artifacts = data["sources"][0]["artifacts"]
            self.assertEqual(artifacts[0]["artifact_type"], "xml")
            self.assertEqual(artifacts[0]["status"], "available")
            self.assertEqual(report.browser_xml_downloaded, 1)
            self.assertEqual(report.pdf_download_attempted, 0)
            self.assertEqual(fetch.call_args.args[0], "https://onlinelibrary.wiley.com/doi/full-xml/10.1002/example")

            report = normalize_source_log_data(
                data,
                project_root=root,
                fetch_fulltext=True,
                parse_local_pdfs=False,
            )
            profile = data["sources"][0]["parse_profile"]

        self.assertGreaterEqual(report.xml_parsed, 1)
        self.assertEqual(profile["fulltext_status"], "parsed_fulltext")
        self.assertEqual(profile["parse_backend"], "xml_text")
        self.assertIn("method", profile["section_summaries"])

    def test_browser_download_without_session_records_pending_action(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "ACM Image Semantic Communication",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "ACM",
                    "venue": "ACM Conference",
                    "year": 2025,
                    "url": "https://doi.org/10.1145/example",
                    "artifacts": [
                        {
                            "artifact_type": "pdf",
                            "uri": "https://dl.acm.org/doi/pdf/10.1145/example",
                            "status": "unknown",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            missing_state = Path(tmp) / "missing_state.json"
            report = normalize_source_log_data(
                data,
                project_root=Path(tmp),
                download_pdfs=True,
                browser_downloads=True,
                browser_session_state=missing_state,
            )

        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(report.browser_download_attempted, 1)
        self.assertEqual(report.browser_downloaded, 0)
        self.assertEqual(report.credential_blocked, 1)
        self.assertEqual(artifact["status"], "pending")
        self.assertIn("session state", artifact["failure_reason"])
        self.assertIn("browser-auth", " ".join(artifact["recovery_actions"]))

    def test_browser_session_rejects_login_html_as_fulltext(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "ScienceDirect Image Semantic Communication",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "Elsevier",
                    "venue": "Physical Communication",
                    "year": 2025,
                    "url": "https://www.sciencedirect.com/science/article/pii/example",
                    "artifacts": [
                        {
                            "artifact_type": "html",
                            "uri": "https://www.sciencedirect.com/science/article/pii/example",
                            "status": "unknown",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "browser_state.json"
            state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            with patch(
                "spiral.literature_ingestion._fetch_with_browser_session",
                return_value=(b"<html><title>Sign in</title><body>Institutional login required</body></html>", "html", "https://login.example"),
            ):
                report = normalize_source_log_data(
                    data,
                    project_root=root,
                    fetch_fulltext=True,
                    browser_downloads=True,
                    browser_session_state=state,
                    skip_unpaywall=True,
                    skip_crossref_fulltext=True,
                )

        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(report.browser_download_attempted, 1)
        self.assertEqual(report.browser_download_failed, 1)
        self.assertEqual(artifact["status"], "failed")
        self.assertIn("login or access-denied", artifact["failure_reason"])
        self.assertFalse(artifact.get("local_path"))

    def test_browser_session_rejects_non_fulltext_html_shell(self) -> None:
        data = {
            "sources": [
                {
                    "id": "s1",
                    "title": "Publisher Shell Page",
                    "type": "academic",
                    "authors": ["A. Author"],
                    "publisher": "ACM",
                    "venue": "ACM Journal",
                    "year": 2025,
                    "url": "https://dl.acm.org/doi/10.1145/example",
                    "artifacts": [
                        {
                            "artifact_type": "html",
                            "uri": "https://dl.acm.org/doi/10.1145/example",
                            "status": "unknown",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "browser_state.json"
            state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            shell = b"<html><body>Publisher page shell PDF link</body></html>" + b" x" * 5000
            with patch(
                "spiral.literature_ingestion._fetch_with_browser_session",
                return_value=(shell, "html", "https://dl.acm.org/doi/10.1145/example"),
            ):
                report = normalize_source_log_data(
                    data,
                    project_root=root,
                    fetch_fulltext=True,
                    browser_downloads=True,
                    browser_session_state=state,
                    skip_unpaywall=True,
                    skip_crossref_fulltext=True,
                )

        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(report.browser_download_failed, 1)
        self.assertEqual(artifact["status"], "failed")
        self.assertIn("complete full-text HTML", artifact["failure_reason"])

    def test_browser_auth_uses_persistent_profile_and_access_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "state.json"
            profile = root / "profile"
            fake_sync_api = types.ModuleType("playwright.sync_api")
            fake_sync_api.sync_playwright = _fake_sync_playwright
            fake_playwright = types.ModuleType("playwright")
            with patch.dict(
                sys.modules,
                {
                    "playwright": fake_playwright,
                    "playwright.sync_api": fake_sync_api,
                },
            ):
                result = save_browser_session_state(
                    start_url="https://ieeexplore.ieee.org/",
                    output=output,
                    user_data_dir=profile,
                    check_url="https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=123456",
                    headless=True,
                    wait_seconds=0,
                )

            self.assertEqual(result["status"], "saved")
            self.assertEqual(result["storage_state"], str(output))
            self.assertEqual(result["user_data_dir"], str(profile))
            self.assertEqual(result["access_check"]["status"], "ok")
            self.assertTrue(result["access_check"]["looks_like_pdf"])
            self.assertTrue(output.exists())
            self.assertTrue(profile.exists())

    def test_browser_fetch_falls_back_to_page_navigation_after_403(self) -> None:
        from spiral.literature_ingestion import _fetch_with_browser_session

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
            fake_sync_api = types.ModuleType("playwright.sync_api")
            fake_sync_api.sync_playwright = _fake_403_sync_playwright
            fake_playwright = types.ModuleType("playwright")
            with patch.dict(
                sys.modules,
                {
                    "playwright": fake_playwright,
                    "playwright.sync_api": fake_sync_api,
                },
            ):
                data, kind, final_url = _fetch_with_browser_session(
                    "https://dl.acm.org/doi/10.1145/example",
                    state,
                    expected_type="html",
                )

        self.assertEqual(kind, "html")
        self.assertIn(b"References", data)
        self.assertEqual(final_url, "https://dl.acm.org/doi/10.1145/example")

    def test_local_html_fulltext_parse_marks_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html_dir = root / "literature" / "html"
            html_dir.mkdir(parents=True)
            html_path = html_dir / "paper.html"
            filler = " image semantic communication digital modulation channel evaluation" * 120
            html_path.write_text(
                f"""
                <html><head><title>Semantic Image Communication Paper</title></head>
                <body>
                <h1>Abstract</h1><p>This paper studies image semantic communication with digital modulation.{filler}</p>
                <h2>Method</h2><p>We propose a joint coding modulation architecture for image semantic transmission.{filler}</p>
                <h2>Experimental Setup</h2><p>Experiments use channel SNR settings, modulation orders, baselines, and image metrics.{filler}</p>
                <h2>Results</h2><p>Results report reconstruction quality, semantic accuracy, and bandwidth savings.{filler}</p>
                <h2>Analysis</h2><p>Ablation and robustness analysis inspect modulation order and channel noise.{filler}</p>
                <h2>Conclusion</h2><p>The method improves semantic image communication under digital modulation.{filler}</p>
                </body></html>
                """,
                encoding="utf-8",
            )
            data = {
                "sources": [
                    {
                        "id": "s1",
                        "title": "Semantic Image Communication Paper",
                        "type": "academic",
                        "authors": ["A. Author"],
                        "venue": "Venue",
                        "year": 2024,
                        "url": "https://example.com/paper",
                        "artifacts": [
                            {
                                "artifact_type": "html",
                                "uri": "https://example.com/paper",
                                "local_path": str(html_path.relative_to(root)),
                                "status": "available",
                            }
                        ],
                    }
                ]
            }

            report = normalize_source_log_data(data, project_root=root, fetch_fulltext=True)

        profile = data["sources"][0]["parse_profile"]
        self.assertEqual(report.html_parsed, 1)
        self.assertEqual(profile["fulltext_status"], "parsed_fulltext")
        self.assertEqual(profile["parse_status"], "complete")
        self.assertEqual(profile["parse_backend"], "html_text")
        self.assertFalse(profile["missing_fields"])
        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(artifact["parse_status"], "parsed")
        self.assertEqual(artifact["parse_backend"], "html_text")

    def test_local_xml_fulltext_parse_marks_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_dir = root / "literature" / "xml"
            xml_dir.mkdir(parents=True)
            xml_path = xml_dir / "paper.xml"
            filler = " image semantic communication digital modulation channel evaluation" * 120
            xml_path.write_text(
                f"""
                <article>
                  <front><article-title>Semantic Image Communication Paper</article-title></front>
                  <abstract><p>This paper studies image semantic communication with digital modulation.{filler}</p></abstract>
                  <body>
                    <sec><title>Method</title><p>We propose a joint coding modulation architecture for image semantic transmission.{filler}</p></sec>
                    <sec><title>Experimental Setup</title><p>Experiments use channel SNR settings, modulation orders, baselines, and image metrics.{filler}</p></sec>
                    <sec><title>Results</title><p>Results report reconstruction quality, semantic accuracy, and bandwidth savings.{filler}</p></sec>
                    <sec><title>Analysis</title><p>Ablation and robustness analysis inspect modulation order and channel noise.{filler}</p></sec>
                  </body>
                </article>
                """,
                encoding="utf-8",
            )
            data = {
                "sources": [
                    {
                        "id": "s1",
                        "title": "Semantic Image Communication Paper",
                        "type": "academic",
                        "authors": ["A. Author"],
                        "venue": "Venue",
                        "year": 2024,
                        "artifacts": [
                            {
                                "artifact_type": "xml",
                                "uri": "https://api.example.test/fulltext.xml",
                                "local_path": str(xml_path.relative_to(root)),
                                "status": "available",
                            }
                        ],
                    }
                ]
            }

            report = normalize_source_log_data(data, project_root=root, fetch_fulltext=True)

        profile = data["sources"][0]["parse_profile"]
        self.assertEqual(report.xml_parsed, 1)
        self.assertEqual(profile["fulltext_status"], "parsed_fulltext")
        self.assertEqual(profile["parse_status"], "complete")
        self.assertEqual(profile["parse_backend"], "xml_text")
        artifact = data["sources"][0]["artifacts"][0]
        self.assertEqual(artifact["parse_status"], "parsed")
        self.assertEqual(artifact["parse_backend"], "xml_text")


def _source(idx: int) -> dict:
    source = {
        "id": f"s{idx}",
        "title": f"Paper {idx}",
        "type": "academic",
        "authors": [f"Author {idx}"],
        "venue": "Test Venue",
        "year": 2024,
        "url": f"https://arxiv.org/abs/2401.0000{idx}",
        "pdf_url": f"https://arxiv.org/pdf/2401.0000{idx}.pdf",
        "credibility": 4,
        "verification": "confirmed",
        "relevance_to_our_gap": "gap_1",
    }
    source.update(_deep_fields(idx))
    return source


def _deep_fields(idx: int) -> dict:
    return {
        "background": f"Background {idx}",
        "contributions": [f"Contribution {idx}"],
        "model": f"Model {idx}",
        "method": f"Method {idx}",
        "experiment_setup": "datasets, metrics, baselines, protocol, and seeds",
        "results": f"Results {idx}",
        "analysis": f"Analysis {idx}",
        "conclusion": f"Conclusion {idx}",
    }


def _search_provenance(source_ids: list[str]) -> dict:
    return {
        "databases": ["public_db", "Semantic Scholar", "arXiv", "internet web search"],
        "inclusion_criteria": ["academic", "has method or experiment evidence"],
        "exclusion_criteria": ["off-topic"],
        "rounds": [
            {
                "round": 1,
                "goal": "breadth",
                "queries": ["topic method"],
                "retrieved_count": 20,
                "screened_count": 10,
                "retained_source_ids": source_ids[:2],
            },
            {
                "round": 2,
                "goal": "depth",
                "queries": ["topic experiment"],
                "retrieved_count": 15,
                "screened_count": 8,
                "retained_source_ids": source_ids[2:4],
            },
            {
                "round": 3,
                "goal": "blindspot",
                "queries": ["topic negative classic"],
                "retrieved_count": 12,
                "screened_count": 7,
                "retained_source_ids": source_ids[4:],
            },
        ],
        "blindspot_checks": {
            "recent_work": "checked",
            "negative_results": "checked",
            "seminal_work": "checked",
            "key_authors": "checked",
            "source_log_consistency": "checked",
        },
        "perspective_coverage": {
            "scenario_task": _perspective(source_ids[:2]),
            "model_method": _perspective(source_ids[1:3]),
            "metric_performance": _perspective(source_ids[2:4]),
            "dataset_protocol": _perspective(source_ids[3:5]),
            "failure_limitation": _perspective(source_ids[1:2] + source_ids[-1:]),
            "baseline_comparison": _perspective(source_ids[:1] + source_ids[-1:]),
        },
    }


def _perspective(source_ids: list[str]) -> dict:
    return {
        "status": "covered",
        "queries": ["query"],
        "source_ids": source_ids,
        "finding": "covered perspective with evidence",
    }


def _gap_map() -> dict:
    return {
        "gap_1": {
            "supporting_sources": ["s1", "s2"],
            "gap_type": "vacancy",
            "level": "large",
            "confidence": "high",
            "description": "Large direction scenario-level gap.",
        },
        "gap_2": {
            "supporting_sources": ["s3", "s4"],
            "gap_type": "enhancement",
            "level": "middle",
            "confidence": "medium",
            "description": "Middle direction method gap.",
        },
        "gap_3": {
            "supporting_sources": ["s2", "s5"],
            "gap_type": "validation",
            "level": "small",
            "confidence": "medium",
            "description": "Small direction validation gap.",
        },
    }


def _fake_sync_playwright() -> "_FakePlaywrightManager":
    return _FakePlaywrightManager()


def _fake_403_sync_playwright() -> "_FakePlaywrightManager":
    return _FakePlaywrightManager(request_cls=_Fake403Request, page_cls=_FakeArticlePage)


class _FakePlaywrightManager:
    def __init__(self, request_cls=None, page_cls=None) -> None:
        self.request_cls = request_cls or _FakeRequest
        self.page_cls = page_cls or _FakePage

    def __enter__(self) -> "_FakePlaywright":
        return _FakePlaywright(self.request_cls, self.page_cls)

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakePlaywright:
    def __init__(self, request_cls=None, page_cls=None) -> None:
        self.chromium = _FakeChromium(request_cls or _FakeRequest, page_cls or _FakePage)


class _FakeChromium:
    def __init__(self, request_cls, page_cls) -> None:
        self.request_cls = request_cls
        self.page_cls = page_cls

    def launch_persistent_context(self, user_data_dir: str, **kwargs) -> "_FakeContext":
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        return _FakeContext(self.request_cls, self.page_cls)

    def launch(self, **kwargs) -> "_FakeBrowser":
        return _FakeBrowser(self.request_cls, self.page_cls)


class _FakeBrowser:
    def __init__(self, request_cls, page_cls) -> None:
        self.request_cls = request_cls
        self.page_cls = page_cls

    def new_context(self, **kwargs) -> "_FakeContext":
        return _FakeContext(self.request_cls, self.page_cls)

    def close(self) -> None:
        return None


class _FakeContext:
    def __init__(self, request_cls=None, page_cls=None) -> None:
        self.request = (request_cls or _FakeRequest)()
        self.page_cls = page_cls or _FakePage

    def new_page(self) -> "_FakePage":
        return self.page_cls()

    def storage_state(self, path: str) -> None:
        Path(path).write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    def close(self) -> None:
        return None


class _FakePage:
    url = "https://example.com"

    def goto(self, *args, **kwargs) -> None:
        if args:
            self.url = args[0]
        return None

    def wait_for_timeout(self, *args, **kwargs) -> None:
        return None

    def wait_for_load_state(self, *args, **kwargs) -> None:
        return None

    def content(self) -> str:
        return "<html><body>Abstract References DOI: 10.0000/example</body></html>"

    def close(self) -> None:
        return None


class _FakeRequest:
    def get(self, url: str, **kwargs) -> "_FakeResponse":
        return _FakeResponse(url)


class _Fake403Request:
    def get(self, url: str, **kwargs) -> "_FakeResponse":
        return _FakeResponse(url, ok=False, status=403, body=b"forbidden", content_type="text/html")


class _FakeResponse:
    def __init__(self, url: str, *, ok: bool = True, status: int = 200, body: bytes = b"%PDF-1.7\nfake authorized content", content_type: str = "application/pdf") -> None:
        self.url = url
        self.ok = ok
        self.status = status
        self._body = body
        self.headers = {"content-type": content_type}

    def body(self) -> bytes:
        return self._body


class _FakeArticlePage(_FakePage):
    def content(self) -> str:
        filler = " semantic communication method results discussion figure table references" * 120
        return (
            "<html><body><article>"
            "<h1>Abstract</h1><p>Abstract text.</p>"
            "<section><h2>Methods</h2><p>Method text.</p></section>"
            "<section><h2>Results</h2><p>Results text with figure and table.</p></section>"
            "<section><h2>References</h2><p>DOI: 10.1145/example.</p></section>"
            f"{filler}</article></body></html>"
        )


if __name__ == "__main__":
    unittest.main()
