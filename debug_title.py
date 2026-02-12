import sys
import re
import json
sys.path.append('.')

# Test the regex pattern directly
with open('html2_sodimac.txt', 'r', encoding='utf-8') as f:
    html = f.read()

print(f"HTML length: {len(html)}")

# Test the flexible pattern
json_ld_pattern = r'<script[^>]*application/ld\+json[^>]*>(.+?)</script>'
json_blocks = re.findall(json_ld_pattern, html, re.DOTALL)

print(f"Found {len(json_blocks)} JSON-LD blocks with flexible pattern")

for i, json_block in enumerate(json_blocks):
    print(f"\nBlock {i+1}:")
    try:
        data = json.loads(json_block)
        print(f"  @type: {data.get('@type')}")
        print(f"  name: {data.get('name')}")
        if isinstance(data, dict) and data.get('@type') == 'product':
            print("  ✅ This is a product!")
            name = data.get('name')
            if name:
                print(f"  ✅ Found title: {name}")
            else:
                print("  ❌ No name field")
        else:
            print("  ❌ Not a product")
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON parse error: {e}")
        print(f"  Raw block (first 200 chars): {json_block[:200]}...")