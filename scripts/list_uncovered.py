import subprocess, sys, re
p = subprocess.run([sys.executable, '-m', 'coverage', 'report', '-m'], capture_output=True, text=True)
lines = p.stdout.splitlines()
low_cover = []
for line in lines[2:]:
    if 'alembic' in line or not line.strip():
        continue
    parts = line.rsplit(None, 3)
    if len(parts) == 4:
        name, stmts, miss, cover = parts
        if cover != '100%' and '.py' in name:
            match = re.search(r'(\d+)%', cover)
            if match:
                pct = int(match.group(1))
                if pct < 100:  # only include < 100%
                    lines_missing = len(set(
                        int(x.strip()) for x in miss.replace('-', ',').split(',') if x.strip() and x[0].isdigit()
                    ))
                    low_cover.append((pct, lines_missing, name))

low_cover.sort()
for pct, lines_missing, name in low_cover[:100]:
    print(f'{pct:3d}%  {lines_missing:3d} lines  {name}')
