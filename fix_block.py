#!/usr/bin/env python
with open(r'D:\Program Files\Downloads\Thesis\traba-hero\backend\app\services\scanner\verification_flow.py', 'r') as f:
    content = f.read()

# Replace the item processing block
old = """    # Build VerificationItem list from parsed anomalies
    items: list[VerificationItem] = []
    for item in parsed["items"]:
        status = item.get("status", "").lower()
        if status not in ("green", "yellow", "red"):
            continue
        items.append(VerificationItem(
            label=item.get("label", "").strip(),
            status=status,
            explanation=item.get("explanation", "").strip(),
            source_title="",
            source_url="",
        ))"""

new = """    # Build VerificationItem list from parsed anomalies
    # lm_client._parse_custom returns anomalies: {flag, reasoning, severity}
    items: list[VerificationItem] = []
    for anomaly in parsed.get("anomalies", []):
        flag = anomaly.get("flag", "").strip()
        reasoning = anomaly.get("reasoning", "").strip()
        severity = anomaly.get("severity", "").lower().strip()
        
        # Map severity to verification status
        status_map = {"high": "red", "medium": "yellow", "low": "yellow", "mid": "yellow"}
        status = status_map.get(severity, "yellow")
        
        # Only add if we have a valid flag and status
        if flag and status:
            items.append(VerificationItem(
                label=flag,
                status=status,
                explanation=reasoning,
                source_title="",
                source_url="",
            ))"""

if old in content:
    content = content.replace(old, new)
    print('Replacement successful')
else:
    print('Old block not found')
    idx = content.find('for item in parsed["items"]:')
    if idx >= 0:
        print(f'Found at {idx}: {content[idx:idx+150]}')

with open(r'D:\Program Files\Downloads\Thesis\traba-hero\backend\app\services\scanner\verification_flow.py', 'w') as f:
    f.write(content)
print("File written")