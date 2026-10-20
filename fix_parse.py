#!/usr/bin/env python
import sys

# Read the file
with open(r'D:\Program Files\Downloads\Thesis\traba-hero\backend\app\services\scanner\verification_flow.py', 'r') as f:
    content = f.read()

# Replace _parse_custom_verify(text) with _parse_custom(text)
old = 'parsed = _parse_custom_verify(text)'
new = 'parsed = _parse_custom(text)'

if old in content:
    content = content.replace(old, new)
    print(f"Replaced '{old}' with '{new}'")
else:
    print(f"Old string not found: '{old}'")
    # Show what's around line 511
    lines = content.split('\n')
    for i, line in enumerate(lines[508:515], start=509):
        print(f"{i}: {line}")

# Write the file back
with open(r'D:\Program Files\Downloads\Thesis\traba-hero\backend\app\services\scanner\verification_flow.py', 'w') as f:
    f.write(content)
print("File written")