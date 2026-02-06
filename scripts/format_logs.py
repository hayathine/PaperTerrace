#!/usr/bin/env python3
import datetime
import json
import sys

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GRAY = "\033[90m"

SEVERITY_COLORS = {
    "DEFAULT": RESET,
    "DEBUG": GRAY,
    "INFO": GREEN,
    "NOTICE": GREEN,
    "WARNING": YELLOW,
    "ERROR": RED,
    "CRITICAL": RED + BOLD,
    "ALERT": RED + BOLD,
    "EMERGENCY": RED + BOLD,
}


def parse_iso_time(timestamp_str):
    """Parses ISO timestamp and returns a datetime object (JST converted)."""
    if not timestamp_str:
        return None
    try:
        # Check if python 3.11+ for fromisoformat with Z
        dt = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    # Convert to JST
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return dt.astimezone(jst)


def format_entry(entry):
    """Formats a single log entry."""
    if not isinstance(entry, dict):
        return str(entry)

    # Extract basic info
    severity = entry.get("severity", "DEFAULT").upper()
    timestamp_str = entry.get("timestamp", "")
    text_payload = entry.get("textPayload", "")
    json_payload = entry.get("jsonPayload", {})
    proto_payload = entry.get("protoPayload", {})
    resource = entry.get("resource", {})

    # Determine timestamp to display
    display_time = ""
    # Try to get app-level timestamp first
    if isinstance(json_payload, dict) and "timestamp" in json_payload:
        dt = parse_iso_time(json_payload["timestamp"])
    else:
        dt = parse_iso_time(timestamp_str)

    if dt:
        display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        display_time = timestamp_str

    # Determine message
    message = ""
    extra_fields = []

    if json_payload:
        if isinstance(json_payload, dict):
            # Try to find message
            if "message" in json_payload:
                message = json_payload["message"]
            elif "event" in json_payload:
                # structlog often puts message in 'event'
                message = json_payload["event"]
            else:
                message = json.dumps(json_payload, ensure_ascii=False)

            # Extract other interesting fields
            ignore_keys = {"timestamp", "message", "event", "severity", "level"}
            for k, v in json_payload.items():
                if k not in ignore_keys:
                    extra_fields.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
        else:
            message = str(json_payload)
    elif text_payload:
        message = text_payload
    elif proto_payload:
        # Handle Cloud Run system logs (e.g. request logs)
        if "@type" in proto_payload:
            message = f"[{proto_payload['@type']}]"

        if "requestMetadata" in proto_payload:
            req = proto_payload["requestMetadata"]
            method = req.get("callerIp", "")
            # protoPayload often has authentication info or request method/url?
            # Cloud Audit Logs structure is complex.
            # Just dump minimal info if possible.
            pass

        # Often Cloud Run HTTP requests are in httpRequest field at root, not protoPayload?
        # Check httpRequest
        pass

    # Check httpRequest at root
    http_request = entry.get("httpRequest", {})
    if http_request and not message:
        method = http_request.get("requestMethod", "")
        url = http_request.get("requestUrl", "")
        status = http_request.get("status", "")
        if method or url:
            message = f"{method} {url} {status}".strip()

    if not message:
        # Fallback to displaying available keys or raw if nothing else
        # Just to avoid empty lines with timestamps
        if not extra_fields:
            # Check for other common fields
            if "labels" in entry:
                extra_fields.append(
                    f"labels={json.dumps(entry['labels'], ensure_ascii=False)}"
                )
            else:
                message = "(No payload)"

    # Colorize
    color = SEVERITY_COLORS.get(severity, RESET)

    # Service name if available
    service = ""
    if "labels" in resource and "service_name" in resource["labels"]:
        svc_name = resource["labels"]["service_name"]
        service = f"[{svc_name}] "

    # Construct output
    output = (
        f"{GRAY}{display_time}{RESET} {color}{severity:<8}{RESET} {service}{message}"
    )

    if extra_fields:
        output += f"\n    {GRAY}{' '.join(extra_fields)}{RESET}"

    return output


def main():
    try:
        # Read all stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            return

        try:
            # Try parsing as whole JSON array/object (gcloud --format=json)
            data = json.loads(input_data)
            if isinstance(data, list):
                # Reverse to show consistent chronological order if needed,
                # but usually we want to keep order from gcloud (newest last or first?)
                # gcloud logs read --limit=50 returns newest first by default? No, usually reverse chronological.
                # Actually gcloud logs read returns events in reverse chronological order (newest first).
                # So we should often reverse it to read top-down chronologically.
                # Let's reverse it for readability.
                for entry in reversed(data):
                    print(format_entry(entry))
            else:
                print(format_entry(data))
        except json.JSONDecodeError:
            # Fallback: try parsing line by line (NDJSON)
            for line in input_data.splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    print(format_entry(entry))
                except json.JSONDecodeError:
                    print(line)  # Raw print if not json

    except Exception as e:
        print(f"Error parsing logs: {e}")


if __name__ == "__main__":
    main()
