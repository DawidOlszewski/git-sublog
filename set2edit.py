import sys, re
p = sys.argv[1]
print(sys.argv)
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(lines)
# znajdź pierwszą niekomentowaną linię i zamień 'pick'->'edit'
for i, line in enumerate(lines):
    s = line.lstrip()
    if not s or s.startswith('#'):
        continue
    lines[i] = re.sub(r'^(pick|p)\b', 'edit', line)
    break
with open(p, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(lines)