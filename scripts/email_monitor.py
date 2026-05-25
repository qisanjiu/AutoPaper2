#!/usr/bin/env python3
"""AutoPaper2 — IMAP 邮箱监控与审稿邮件解析脚本

监控指定邮箱，等待并提取 paperreview.ai 的审稿邮件。

支持 QQ 邮箱（imap.qq.com，端口 993，SSL）。
注意：QQ 邮箱需要使用 IMAP/SMTP 授权码，不是登录密码。

用法:
    python scripts/email_monitor.py \
        --email 1497678847@qq.com \
        --password "YOUR_IMAP_AUTH_CODE" \
        --sender-filter "noreply@paperreview.ai" \
        --output knowledge/M6/M6S03_review_email.json \
        --wait-timeout 3600 \
        --poll-interval 60
"""

from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


DEFAULT_IMAP_SERVER = "imap.qq.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_EMAIL = "1497678847@qq.com"
DEFAULT_WAIT_TIMEOUT = 3600  # 1 hour
DEFAULT_POLL_INTERVAL = 60  # 1 minute


def _load_email_config(config_path: Optional[Path]) -> dict:
    path = config_path or Path("config") / "email_config.yaml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data.get("email", data) or {}


def _resolve_secret(value: str | None) -> str | None:
    if not value:
        return value
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def parse_email_body(msg: email.message.EmailMessage) -> dict:
    """Extract text body and metadata from an email message."""
    subject = msg.get("Subject", "")
    from_addr = msg.get("From", "")
    date_str = msg.get("Date", "")
    message_id = msg.get("Message-ID", "")

    bodies: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        bodies.append(payload.decode(charset, errors="replace"))
                except Exception:
                    pass
            elif content_type == "text/html":
                # Prefer plain text, but keep HTML as fallback
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        bodies.append(payload.decode(charset, errors="replace"))
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                bodies.append(payload.decode(charset, errors="replace"))
        except Exception:
            pass

    body_text = "\n\n".join(bodies).strip()

    return {
        "subject": subject,
        "from": from_addr,
        "date": date_str,
        "message_id": message_id,
        "body": body_text,
        "body_length": len(body_text),
    }


def search_review_email(
    email_addr: str,
    password: str,
    imap_server: str,
    imap_port: int,
    sender_filter: str,
    subject_filter: Optional[str],
    wait_timeout: int,
    poll_interval: int,
    unread_only: bool,
) -> dict:
    """Poll IMAP inbox and return the first matching review email.

    Returns a dict with status and email data.
    """
    result = {
        "status": "unknown",
        "checked_at": datetime.now().isoformat(),
        "email": email_addr,
        "sender_filter": sender_filter,
        "wait_timeout_seconds": wait_timeout,
        "poll_interval_seconds": poll_interval,
        "found_email": None,
        "message": "",
    }

    start_time = time.time()
    attempt = 0

    while True:
        attempt += 1
        elapsed = int(time.time() - start_time)
        remaining = wait_timeout - elapsed

        if remaining <= 0:
            result["status"] = "timeout"
            result["message"] = (
                f"No review email found within {wait_timeout}s "
                f"after {attempt} polling attempts."
            )
            return result

        print(f"[email-monitor] Poll #{attempt} (elapsed {elapsed}s, remaining {remaining}s)")

        mail: Optional[imaplib.IMAP4_SSL] = None
        try:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_addr, password)
            mail.select("inbox")

            # Build search criteria
            search_criteria = []
            if unread_only:
                search_criteria.append("UNSEEN")
            if sender_filter:
                search_criteria.append(f'FROM "{sender_filter}"')
            if subject_filter:
                search_criteria.append(f'SUBJECT "{subject_filter}"')

            if search_criteria:
                criterion = "(" + " ".join(search_criteria) + ")"
            else:
                criterion = "ALL"

            status, data = mail.search(None, criterion)
            if status != "OK":
                print(f"[email-monitor] Search failed: {status}")
                mail.logout()
                time.sleep(poll_interval)
                continue

            msg_ids = data[0].split()
            if not msg_ids:
                print("[email-monitor] No matching emails yet.")
                mail.logout()
                time.sleep(min(poll_interval, remaining))
                continue

            # Fetch the latest matching email
            latest_id = msg_ids[-1]
            status, fetch_data = mail.fetch(latest_id, "(RFC822)")
            if status != "OK" or not fetch_data:
                print(f"[email-monitor] Fetch failed for msg {latest_id}")
                mail.logout()
                time.sleep(poll_interval)
                continue

            raw_email = fetch_data[0][1]
            msg = email.message_from_bytes(raw_email)
            parsed = parse_email_body(msg)

            # Optionally mark as read (best-effort)
            try:
                mail.store(latest_id, "+FLAGS", "\\Seen")
            except Exception:
                pass

            result["status"] = "success"
            result["message"] = f"Found review email after {attempt} attempts ({elapsed}s)."
            result["found_email"] = parsed
            result["found_at"] = datetime.now().isoformat()

            mail.logout()
            return result

        except imaplib.IMAP4.error as exc:
            result["status"] = "imap_error"
            result["message"] = f"IMAP error: {exc}"
            print(f"[email-monitor] IMAP error: {exc}", file=sys.stderr)
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass
            # Don't return immediately; allow retry for transient errors
        except Exception as exc:
            result["status"] = "error"
            result["message"] = f"Unexpected error: {exc}"
            print(f"[email-monitor] Error: {exc}", file=sys.stderr)
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass

        # Wait before next poll
        sleep_time = min(poll_interval, remaining)
        if sleep_time > 0:
            time.sleep(sleep_time)

    # Should never reach here
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor IMAP inbox for paperreview.ai review emails"
    )
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Email address")
    parser.add_argument("--password", default=None, help="IMAP password / auth code")
    parser.add_argument("--imap-server", default=DEFAULT_IMAP_SERVER, help="IMAP server")
    parser.add_argument("--imap-port", type=int, default=DEFAULT_IMAP_PORT, help="IMAP port")
    parser.add_argument("--sender-filter", default="noreply@paperreview.ai", help="Filter by sender")
    parser.add_argument("--subject-filter", default=None, help="Filter by subject keyword")
    parser.add_argument("--output", required=True, help="Path to write parsed email JSON")
    parser.add_argument("--wait-timeout", type=int, default=DEFAULT_WAIT_TIMEOUT, help="Max wait time in seconds")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help="Polling interval in seconds")
    parser.add_argument("--unread-only", action="store_true", help="Only check unread emails")
    parser.add_argument("--config", default=None, help="Optional email config YAML path")
    args = parser.parse_args()

    email_cfg = _load_email_config(Path(args.config) if args.config else None)
    email_addr = args.email
    if email_addr == DEFAULT_EMAIL:
        email_addr = email_cfg.get("address", email_addr)
    imap_server = args.imap_server
    if imap_server == DEFAULT_IMAP_SERVER:
        imap_server = email_cfg.get("imap_server", imap_server)
    imap_port = args.imap_port
    if imap_port == DEFAULT_IMAP_PORT:
        imap_port = int(email_cfg.get("imap_port", imap_port))
    sender_filter = args.sender_filter
    if sender_filter == "noreply@paperreview.ai":
        sender_filter = email_cfg.get("sender_filter", sender_filter)
    password = args.password or _resolve_secret(email_cfg.get("password"))
    if not password:
        print("[email-monitor] ERROR: IMAP password / auth code not provided.", file=sys.stderr)
        return 1

    print(f"[email-monitor] Starting monitor for {email_addr}")
    print(f"[email-monitor] IMAP server: {imap_server}:{imap_port}")
    print(f"[email-monitor] Sender filter: {sender_filter}")
    print(f"[email-monitor] Wait timeout: {args.wait_timeout}s")

    result = search_review_email(
        email_addr=email_addr,
        password=password,
        imap_server=imap_server,
        imap_port=imap_port,
        sender_filter=sender_filter,
        subject_filter=args.subject_filter,
        wait_timeout=args.wait_timeout,
        poll_interval=args.poll_interval,
        unread_only=args.unread_only,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[email-monitor] Status: {result['status']}")
    print(f"[email-monitor] Message: {result['message']}")
    print(f"[email-monitor] Result saved to: {output_path}")

    if result["status"] == "success":
        return 0
    elif result["status"] == "timeout":
        return 3  # distinguish timeout from error
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
