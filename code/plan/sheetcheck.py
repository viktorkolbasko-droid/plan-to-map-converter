# Sheet class guard - the first step of run.sh (code 007, Р16; plan/00, step 1: the route goes by the class of the sheet).
#   A sheet of another class does not run the Revit pipeline (client-b, floor 40, test 2: run.sh on an AutoCAD sheet with
#   layers, 67 min). Code 011 (package 5, Б2 and Б3 of the measurer «12»): the class goes by signs of the file that name
#   its source application, not by the virtual printer or by any OCG layer:
#   - Revit (exit 0): the title is the path of a Revit model (a Windows path - UNC \\server\... or X:\... - with «revit» in
#     it, or any title with «.rvt»), or the print signature of Revit itself (producer or creator «Revit»). PDF24 or
#     Ghostscript alone is a virtual printer any program prints through (Б2: «Unirus МСК план 2 эт» - PDF24, no model path,
#     2.5 % zero-length strokes against 60-69 % of the Revit sheets of client A) - not a sign of Revit;
#   - the layer route (exit 4, ocg/run_ocg.sh): OCG layers AND a sign of a CAD drawing - the producer or creator of a CAD
#     program (AutoCAD plotter pdfplot…, AutoCAD, ODA PDF Export / Teigha, ARCHICAD / Graphisoft, gcad / GstarCAD
#     pdf-hc.hdi, nanoCAD, BricsCAD, ZWCAD, DraftSight, progeCAD, IntelliCAD, MicroStation / Bentley, Vectorworks, Allplan)
#     or a layer of a DWG drawing among the OCG layers: «0» (the layer every DWG has) or an xref layer bound into the drawing
#     («…$0$…»). A PDF of a design program with layers (CorelDRAW «Слой 1», Illustrator «Layer 1» - Б3) is not CAD: a stop;
#   - a CAD sheet without OCG layers: the layer route cannot read it (its first step Э2 needs the layers - ПК3-П12) - a stop;
#   - otherwise the class is unknown - a stop with a question to the owner with a picture (plan/00, steps 1 and 8).
#   After the owner's answer: cfg.SHEET_CLASS = 'revit' - the Revit route; cfg.SHEET_CLASS = 'layers' (code 011) - the layer
#   route for a sheet with OCG layers without a CAD sign. A sheet with OCG layers and a CAD sign goes to the layer route
#   whatever SHEET_CLASS says - its layers are the source.
#   python3 sheetcheck.py [pdf]      (floor folder; the PDF is cfg.PDF, else the only *.pdf in the folder)
# Exit 0 - a Revit sheet; 4 - a CAD sheet with OCG layers, the layer route; 3 - stop: the reason is printed and written
#   to sheetcheck.json (route 'unknown').
import os, sys, re, json, glob, importlib.util
import pymupdf as fitz
# a CAD program in the producer or the creator of the PDF (code 011, Б3). Seen on the training samples «12»: pdfplot /
#   AutoCAD (5 sheets), ARCHICAD (6), ODA PDF Export (2), gcad pdf-hc.hdi (1); the other names - the same kind of sign
#   (a CAD program that writes DWG layers into OCG), no sample yet. PDFTron alone is a PDF library, not a CAD sign.
CAD_RE = re.compile(r'pdfplot|autocad|oda pdf|teigha|archicad|graphisoft|\bgcad\b|gstarcad|pdf-hc\.hdi|nanocad|bricscad|zwcad|'
                    r'draftsight|progecad|intellicad|microstation|bentley|vectorworks|allplan', re.I)
VIRTUAL_RE = re.compile(r'pdf24|ghostscript', re.I)          # virtual printers: recorded, not a sign of the class
def floor_pdf():
    if len(sys.argv) > 1: return sys.argv[1], None
    cfg = None
    if os.path.exists('cfg.py'):
        try:
            sp = importlib.util.spec_from_file_location('cfg', 'cfg.py'); cfg = importlib.util.module_from_spec(sp); sp.loader.exec_module(cfg)
            if getattr(cfg, 'PDF', None): return cfg.PDF, cfg
        except Exception as ex: print('cfg.py not read:', ex)
    pdfs = sorted(glob.glob('*.pdf'))
    return (pdfs[0] if len(pdfs) == 1 else None), cfg
def decode_title(t):
    """PyMuPDF leaves a title written as a hex string undecoded: <5C5C64...> - cp1251 or UTF-16 bytes of the model path"""
    m = re.fullmatch(r'<([0-9A-Fa-f\s]+)>?', (t or '').strip())
    if not m: return t or ''
    h = re.sub(r'\s', '', m.group(1)); b = bytes.fromhex(h[:len(h) // 2 * 2])
    for enc in (('utf-16',) if b[:2] in (b'\xfe\xff', b'\xff\xfe') else ()) + ('cp1251', 'latin-1'):
        try: return b.decode(enc)
        except Exception: pass
    return t
def revit_signs(prod, crea, title):
    """(model path in the title, print signature of Revit) - plan/rules/10 §1"""
    path = bool(re.match(r'^(\\\\[^\\]+\\|[A-Za-z]:[\\/])', title.strip()))
    model = bool(re.search(r'\.rvt\b', title, re.I)) or (path and bool(re.search(r'revit', title, re.I)))
    printed = bool(re.search(r'revit', prod + ' ' + crea, re.I))
    return model, printed
def dwg_layers(names):
    """OCG layers of a DWG drawing: «0» - the layer every DWG has; «…$0$…» - an xref layer bound into the drawing; the prefix
    «PDF _» / «PDF_» an AutoCAD PDF import puts before the names is taken off"""
    out = []
    for n in names:
        b = re.sub(r'^PDF\s?_', '', (n or '').strip())
        if b == '0' or '$0$' in b: out.append(n)
    return out
if __name__ == '__main__':
    pdf, cfg = floor_pdf()
    res = dict(pdf=pdf, route='revit', ok=True, reasons=[])
    sc = getattr(cfg, 'SHEET_CLASS', None)
    if not pdf or not os.path.exists(pdf):
        res.update(ok=False, route='unknown', reasons=[f'исходник не найден: {pdf or "в папке нет единственного *.pdf и нет cfg.PDF"}'])
    else:
        doc = fitz.open(pdf); md = doc.metadata or {}
        prod, crea, title = md.get('producer') or '', md.get('creator') or '', decode_title(md.get('title'))
        try: ocgs = doc.get_ocgs() or {}
        except Exception: ocgs = {}
        names = sorted({v.get('name', '') for v in ocgs.values()})
        model, printed = revit_signs(prod, crea, title)
        cad = CAD_RE.search(prod + ' ' + crea); dl = dwg_layers(names)
        signs = dict(revit_model_path=model, revit_print=printed, virtual_printer=bool(VIRTUAL_RE.search(prod + ' ' + crea)),
                     cad_program=cad.group(0) if cad else None, dwg_layers=dl[:5], sheet_class_cfg=sc)
        res.update(producer=prod, creator=crea, title=title[:200], ocg_layers=len(ocgs), ocg_names=names[:20], pages=doc.page_count, signs=signs)
        what = f'producer «{prod}», creator «{crea}»'
        if ocgs and (cad or dl):
            res.update(ok=False, route='layers', sheet_class='cad-layers')
            res['reasons'].append(f'лист CAD со слоями: {what}, слоёв OCG {len(ocgs)}, признак CAD — '
                                  + (f'программа «{cad.group(0)}»' if cad else f'слой чертежа DWG {dl[:3]}')
                                  + ' — маршрут по слоям, модуль ocg/ (plan/00, шаг 1; код 011)')
        elif ocgs and sc == 'layers':
            res.update(ok=False, route='layers', sheet_class='layers-by-owner')
            res['reasons'].append(f'слои OCG ({len(ocgs)}) без признака CAD, {what}: маршрут по слоям по ответу владельца (cfg.SHEET_CLASS = \'layers\')')
        elif ocgs and sc != 'revit':
            res.update(ok=False, route='unknown', sheet_class='layers-not-cad')
            res['reasons'].append(f'в листе слои OCG ({len(ocgs)}: {names[:4]}), но признака CAD нет: {what}, слоя чертежа DWG «0» нет — '
                                  'маршрут по слоям — для листа CAD (Б3): вопрос владельцу картинкой (plan/00, шаги 1 и 8); после ответа — '
                                  'cfg.SHEET_CLASS = \'layers\' или \'revit\'')
        elif not ocgs and cad and sc != 'revit':
            res.update(ok=False, route='unknown', sheet_class='cad-no-layers')
            res['reasons'].append(f'лист CAD без слоёв OCG ({what}): маршрут по слоям его не прочтёт — Э2 нужны слои (ПК3-П12), '
                                  'Revit-маршрут — для листа Revit: вопрос владельцу картинкой (plan/00, шаги 1 и 8)')
        elif not (model or printed) and sc != 'revit':
            res.update(ok=False, route='unknown', sheet_class='unknown')
            res['reasons'].append(f'класс листа не определён: {what}, в title нет пути модели Revit, подписи печати Revit нет'
                                  + (' (PDF24 и Ghostscript — виртуальный принтер любой программы, не признак Revit — Б2)' if signs['virtual_printer'] else '')
                                  + ' — вопрос владельцу картинкой (plan/00, шаги 1 и 8); после ответа — cfg.SHEET_CLASS = \'revit\'')
        else:
            res['sheet_class'] = 'revit' if (model or printed) else 'revit-by-owner'
    json.dump(res, open('sheetcheck.json', 'w'), ensure_ascii=False, indent=1)
    if res['ok']:
        print('sheet: Revit -', res.get('producer'), '|', res.get('creator'), '| OCG', res.get('ocg_layers'), '|', res.get('sheet_class'))
        sys.exit(0)
    if res['route'] == 'layers':
        print('sheet: CAD со слоями OCG -', res.get('producer'), '| OCG', res.get('ocg_layers'), '— маршрут по слоям ocg/')
        sys.exit(4)
    print('СТОП: лист не для run.sh —', '; '.join(res['reasons']))
    sys.exit(3)
