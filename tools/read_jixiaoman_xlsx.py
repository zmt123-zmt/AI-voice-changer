# -*- coding: utf-8 -*-
"""读取姬小满.xlsx，对比 C 列与原始 ASR 差异，输出最终训练 list"""
import zipfile, re
from xml.etree import ElementTree as ET
from pathlib import Path

XLSX = Path(r"C:\Users\ASUS\Documents\AI换声\data\asr_out\姬小满.xlsx")
ASR_LIST = Path(r"C:\Users\ASUS\Documents\AI换声\data\asr_out\姬小满_武道奇才\武道奇才 姬小满.list")
OUT = Path(r"C:\Users\ASUS\Documents\AI换声\data\asr_out\姬小满_武道奇才_final.list")

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
z = zipfile.ZipFile(XLSX)
sst = []
root = ET.fromstring(z.read('xl/sharedStrings.xml'))
for si in root.iter(M+'si'):
    sst.append(''.join(t.text or '' for t in si.iter(M+'t')))
root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
rows = []
for row in root.iter(M+'row'):
    cells = {}
    for c in row.iter(M+'c'):
        ref = c.attrib.get('r', '')
        col = re.match(r'[A-Z]+', ref).group(0)
        t = c.attrib.get('t')
        v = c.find(M+'v')
        if t == 's' and v is not None:
            cells[col] = sst[int(v.text)]
        elif v is not None:
            cells[col] = v.text
        else:
            isl = c.find(M+'is')
            cells[col] = ''.join(tt.text or '' for tt in isl.iter(M+'t')) if isl is not None else ''
    rows.append(cells)

# 原始 ASR
orig = {}
for line in ASR_LIST.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    p = line.split('|')
    if len(p) >= 4:
        orig[Path(p[0]).name] = '|'.join(p[3:])

with open('data/asr_out/diff_report.txt', 'w', encoding='utf-8') as out:
    out.write("=== 用户修改对比（C列 vs 原始ASR） ===\n")
    changed = []
    for r in rows[1:]:
        fname = (r.get('B') or '').strip()
        cval = (r.get('C') or '').strip()
        if not fname:
            continue
        if cval and fname in orig and cval != orig[fname]:
            changed.append(fname)
            out.write(f"【改】{fname}\n  原: {orig[fname]}\n  新: {cval}\n")
        elif not cval:
            out.write(f"【空】{fname}\n")
    # 生成 final list
    lines = []
    for r in rows[1:]:
        fname = (r.get('B') or '').strip()
        cval = (r.get('C') or '').strip()
        if not fname or not cval:
            continue
        # 用原始路径
        for line in ASR_LIST.read_text(encoding='utf-8').splitlines():
            if line.split('|') and Path(line.split('|')[0]).name == fname:
                path = line.split('|')[0]
                break
        lines.append(f"{path}|姬小满|ZH|{cval}")
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    out.write(f"\n=== 统计 ===\n总行: {len(rows)-1}, 修改: {len(changed)}, 输出list: {len(lines)}\n")

print("done")
