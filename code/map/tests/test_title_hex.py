"""Тест приёма: dc:title — hex-строка cp1251, обрезанная на полубайте (П3 «Признаки происхождения векторного PDF»), — путь модели и признак Revit.
Без внешних данных: PDF собирается здесь. Запуск из любой папки: python3 tests/test_title_hex.py — код 0, если всё совпало. Код v007."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # code/ — без PYTHONPATH (К4, К5)
import pymupdf
from source_intake import intake, decode_title

path = r'\\dfs.ga.loc\Share\exp\expansion\клиент А\REVIT\клиент А этаж_ФХ_.rvt'
hx = path.encode('cp1251').hex().upper()
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)

check('hex cp1251 целиком', decode_title('<' + hx + '>'), (path, 'hex-cp1251'))
check('hex cp1251, обрезан на полубайте', decode_title('<' + hx[:-1]), (path[:-1], 'hex-cp1251'))
check('hex utf-8', decode_title('<' + path.encode('utf-8').hex() + '>'), (path, 'hex-utf8'))
check('обычный текст', decode_title('План 5 этажа'), ('План 5 этажа', 'text'))
check('короткое hex-похожее слово — текст', decode_title('CAFE'), ('CAFE', 'text'))
with tempfile.TemporaryDirectory() as td:
    pdf = os.path.join(td, 'title_hex.pdf'); doc = pymupdf.open(); pg = doc.new_page(width=600, height=400)
    for i in range(700): pg.draw_line((10 + i % 50 * 10, 10 + i // 50 * 20), (15 + i % 50 * 10, 10 + i // 50 * 20))   # вектор: отрезков больше порога
    doc.set_metadata({'title': '<' + hx[:-1]}); doc.save(pdf); doc.close()
    rep = intake(pdf, os.path.join(td, 'out'))
    p = rep.get('pdf', {})
    check('intake: путь модели', p.get('model_path'), path[:-1])
    check('intake: признак Revit', p.get('revit_sign'), True)
    check('intake: способ', p.get('title_decoded'), 'hex-cp1251')
    md = open(os.path.join(td, 'out', 'intake.md'), encoding='utf-8').read()
    check('intake.md: строка пути модели', 'Путь модели' in md and 'признак Revit' in md, True)
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
