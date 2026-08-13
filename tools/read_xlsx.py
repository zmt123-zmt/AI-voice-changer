import zipfile, re, sys
from xml.etree import ElementTree as ET

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def read_xlsx(path):
    z = zipfile.ZipFile(path)
    # shared strings
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall('m:si', NS):
            sst.append(''.join(t.text or '' for t in si.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')))
    # first sheet
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    sheet_name = wb.find('m:sheets/m:sheet', NS).attrib['name']
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rid = wb.find('m:sheets/m:sheet', NS).attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
    target = None
    for rel in rels:
        if rel.attrib['Id'] == rid:
            target = rel.attrib['Target']
    if target.startswith('/'):
        target = target[1:]
    else:
        target = 'xl/' + target
    root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
        cells = {}
        for c in row.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
            ref = c.attrib.get('r', '')
            col = re.match(r'[A-Z]+', ref).group(0)
            t = c.attrib.get('t')
            v = c.find('m:v', NS)
            if t == 's' and v is not None:
                cells[col] = sst[int(v.text)]
            elif v is not None:
                cells[col] = v.text
            else:
                cells[col] = ''
        rows.append(cells)
    return sheet_name, rows

sheet, rows = read_xlsx(sys.argv[1])
print(f"sheet: {sheet}, 行数: {len(rows)}")
for i, r in enumerate(rows):
    vals = [r.get(c, '') for c in ['A','B','C','D','E','F']]
    print(f"R{i}: " + " | ".join(vals))
