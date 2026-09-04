import subprocess, sys
p = subprocess.run([sys.executable, '-m', 'coverage', 'report', '-m'], capture_output=True, text=True)
lines = p.stdout.splitlines()
for line in lines[2:]:
    if not line.strip():
        continue
    parts = line.rsplit(None, 3)
    if len(parts) == 4:
        name, stmts, miss, cover = parts
        if cover != '100%':
            print(f"{cover}\t{miss}\t{stmts}\t{name}")
    else:
        # print lines that don't match expected format for inspection
        print(line)
