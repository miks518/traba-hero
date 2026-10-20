#!/usr/bin/env python
with open(r'D:\Program Files\Downloads\Thesis\traba-hero\backend\app\services\scanner\verification_flow.py', 'r') as f:
    content = f.read()

# Add None check after parsed = _parse_custom(text)
# Find the line and add check after it
old_line = '    parsed = _parse_custom(text)'
new_lines = '''    parsed = _parse_custom(text)
    # Handle empty/None response from parser
    if parsed is None:
        return ([], "", "", False, [], None, None, "", [])'''

if old_line in content:
    content = content.replace(old_line, new_lines)
    print("Added None check successfully")
else:
    print("Old line not found")
    # Show what's around line 511
    lines = content.split('\n')
    for i, line in enumerate(lines[508:520], start=509):
        print(f"{i}: {line}")

with open(r'D:\Program Files\Downloads\Thesis\traba-hero\backend\app\services\scanner\verification_flow.py', 'w') as f:
    f.write(content)
print("File written")