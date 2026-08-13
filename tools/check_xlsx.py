# -*- coding: utf-8 -*-
import zipfile, re, sys
from xml.etree import ElementTree as ET
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def read_all(path):
    z = zipfile.ZipFile(path)
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.iter(M+'si'):
            sst.append(''.join(t.text or '' for t in si.iter(M+'t')))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    sheets = wb.find(M+'sheets')
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.attrib['Id']: r.attrib['Target'] for r in rels}
    for sh in sheets.iter(M+'sheet'):
        name = sh.attrib['name']
        rid = sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        tgt = relmap[rid]
        if tgt.startswith('/'): tgt = tgt[1:]
        else: tgt = 'xl/' + tgt
        root = ET.fromstring(z.read(tgt))
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
                    if isl is not None:
                        cells[col] = ''.join(tt.text or '' for tt in isl.iter(M+'t'))
                    else:
                        cells[col] = ''
            rows.append(cells)
        yield name, rows

path = sys.argv[1]
with open('data/asr_out/col_report.txt', 'w', encoding='utf-8') as out:
    for name, rows in read_all(path):
        out.write(f"=== Sheet: {name}, 数据行: {len(rows)-1} ===\n")
        # 表头
        if rows:
            out.write("表头: " + " | ".join(rows[0].get(c,'') for c in ['A','B','C','D','E','F']) + "\n")
        # 每列非空统计
        from collections import Counter
        colcount = Counter()
        filled_d = 0
        for r in rows[1:]:
            for c in ['A','B','C','D','E','F']:
                if (r.get(c) or '').strip():
                    colcount[c] += 1
        out.write(f"各列非空: {dict(colcount)}\n")
        # D列有内容的行
        d_rows = [i+1 for i, r in enumerate(rows[1:]) if (r.get('D') or '').strip()]
        out.write(f"D列(校对台词)已填行号: {d_rows}\n")
        # 检查有没有别的非空列(如G,H)
        for i, r in enumerate(rows[1:], 1):
            extra = {c: v for c, v in r.items() if c not in 'ABCDEF' and (v or '').strip()}
            if extra:
                out.write(f"行{i} 额外列: {extra}\n")
print("done")
