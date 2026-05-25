#!/usr/bin/env python3
"""AutoPaper2 — paperreview.ai 自动提交脚本

使用 Playwright 模拟浏览器自动提交论文 PDF 到 https://paperreview.ai

依赖:
    pip install playwright
    playwright install chromium

用法:
    python scripts/paperreview_uploader.py \
        --pdf artifacts/paper.pdf \
        --email 1497678847@qq.com \
        --venue "ICLR" \
        --output knowledge/M6/M6S02_submission_log.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import yaml


PAPERREVIEW_URL = "https://paperreview.ai/"
DEFAULT_EMAIL = "1497678847@qq.com"
DEFAULT_TIMEOUT = 120_000  # 120s page load timeout


def _load_email_config(config_path: Optional[Path]) -> dict:
    path = config_path or Path("config") / "email_config.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data.get("email", data) or {}


def _check_playwright() -> bool:
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


def _install_hint() -> str:
    return (
        "Playwright 未安装。请执行以下命令安装:\n"
        "  pip install playwright\n"
        "  playwright install chromium\n"
        "然后重新运行本脚本。"
    )


def submit_paper(
    pdf_path: Path,
    email: str,
    venue: Optional[str],
    headless: bool,
    timeout: int,
) -> dict:
    """Submit paper to paperreview.ai using Playwright.

    Returns a dict with status and metadata.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

    result = {
        "platform": "paperreview.ai",
        "url": PAPERREVIEW_URL,
        "submitted_at": datetime.now().isoformat(),
        "pdf_path": str(pdf_path),
        "email": email,
        "venue": venue,
        "status": "unknown",
        "message": "",
        "tracking": {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(timeout)

        try:
            # 1. Open the site
            page.goto(PAPERREVIEW_URL, wait_until="networkidle")
            time.sleep(2)

            # 2. Handle cookie consent if present (best-effort)
            try:
                consent_btn = page.locator(
                    "button:has-text('Accept'), button:has-text('同意'), "
                    "button:has-text('Allow'), button:has-text('OK')"
                ).first
                if consent_btn.is_visible(timeout=3000):
                    consent_btn.click()
                    time.sleep(1)
            except Exception:
                pass

            # 3. Locate file input and upload PDF
            # The site uses a drag-drop zone; the actual input is usually <input type="file">
            file_input = page.locator("input[type='file']").first
            if not file_input.count():
                result["status"] = "failed"
                result["message"] = "Could not locate file upload input on the page."
                browser.close()
                return result

            file_input.set_input_files(str(pdf_path.resolve()))
            time.sleep(3)  # Wait for upload/progress

            # 4. Fill email
            email_input = page.locator("input[type='email']").first
            if email_input.count():
                email_input.fill(email)
                time.sleep(0.5)
            else:
                # Try placeholder-based heuristic
                for inp in page.locator("input").all():
                    placeholder = inp.get_attribute("placeholder") or ""
                    if "email" in placeholder.lower() or "邮箱" in placeholder:
                        inp.fill(email)
                        time.sleep(0.5)
                        break

            # 5. Select venue (optional)
            if venue:
                # Try to find a select or combobox
                select_locator = page.locator("select").first
                if select_locator.count():
                    try:
                        select_locator.select_option(label=venue)
                        time.sleep(0.5)
                    except Exception:
                        # Fallback: try contains text
                        pass
                else:
                    # Try input with venue-related attributes
                    for inp in page.locator("input").all():
                        placeholder = inp.get_attribute("placeholder") or ""
                        if "venue" in placeholder.lower() or "conference" in placeholder.lower():
                            inp.fill(venue)
                            time.sleep(0.5)
                            break

            # 6. Click submit
            submit_btn = page.locator(
                "button[type='submit'], button:has-text('Submit'), "
                "button:has-text('Upload'), button:has-text('提交')"
            ).first
            if submit_btn.count():
                submit_btn.click()
            else:
                result["status"] = "failed"
                result["message"] = "Could not locate submit button."
                browser.close()
                return result

            # 7. Wait for confirmation
            time.sleep(5)
            page_content = page.content()

            # Heuristic success detection
            success_indicators = [
                "submitted",
                "success",
                "thank you",
                "uploaded",
                "review",
                "notification",
                "submitted successfully",
            ]
            failed_indicators = [
                "error",
                "failed",
                "invalid",
                "too large",
                "max 10mb",
            ]

            page_text_lower = page_content.lower()
            success = any(ind in page_text_lower for ind in success_indicators)
            failed = any(ind in page_text_lower for ind in failed_indicators)

            if failed and not success:
                result["status"] = "failed"
                result["message"] = "Submission page indicated an error."
            elif success:
                result["status"] = "success"
                result["message"] = "Paper submitted successfully to paperreview.ai."
            else:
                result["status"] = "unknown"
                result["message"] = "Could not determine submission status from page content."

            # Try to extract any confirmation text
            result["page_snapshot"] = page_text_lower[:2000]

            browser.close()

        except PWTimeoutError:
            result["status"] = "failed"
            result["message"] = f"Page operation timed out after {timeout}ms."
            try:
                browser.close()
            except Exception:
                pass
        except Exception as exc:
            result["status"] = "failed"
            result["message"] = f"Unexpected error: {exc}"
            try:
                browser.close()
            except Exception:
                pass

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit a paper PDF to paperreview.ai"
    )
    parser.add_argument("--pdf", required=True, help="Path to the paper PDF")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Email address for review notification")
    parser.add_argument("--venue", default=None, help="Target venue (optional)")
    parser.add_argument("--output", required=True, help="Path to write submission log JSON")
    parser.add_argument("--config", default=None, help="Optional email config YAML path")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser in headless mode")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="Show browser window")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Page timeout in ms")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    # Size check (paperreview.ai limit is ~10MB)
    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if size_mb > 10:
        print(f"WARNING: PDF size is {size_mb:.1f} MB, exceeding 10 MB limit.", file=sys.stderr)

    if not _check_playwright():
        print(_install_hint(), file=sys.stderr)
        return 2

    email_cfg = _load_email_config(Path(args.config) if args.config else None)
    email_addr = args.email
    if email_addr == DEFAULT_EMAIL:
        email_addr = email_cfg.get("address", email_addr)
    venue = args.venue or email_cfg.get("venue") or email_cfg.get("venue_id")

    print(f"[paperreview.ai] Submitting {pdf_path} ...")
    result = submit_paper(
        pdf_path=pdf_path,
        email=email_addr,
        venue=venue,
        headless=args.headless,
        timeout=args.timeout,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[paperreview.ai] Status: {result['status']}")
    print(f"[paperreview.ai] Log saved to: {output_path}")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
