#!/usr/bin/env python3
"""quote_check.py — сверка цитат «Было / Стало» предложения с нынешним текстом документов.

Назначение
    Перед вливанием предложения каждое «Было» (или якорь «вставить после «…»»)
    должно стоять в нынешнем тексте документа дословно и ровно один раз
    (core/rules/40 §6; proposals/both/2026-10-09-два-чата-и-приёмка-изменений.md §3.1–3.2;
    ОЧ-74). Скрипт находит каждое «Было» и считает вхождения: 0, 1 или больше.
    С ключом --after проверяет «Стало» — после вливания каждое «Стало» есть ровно один раз.

Запуск
    python3 quote_check.py <файл предложения> <папка документов> [--after] [--allow-nodoc]

    <папка документов> — текущие тексты документов проекта, каждый в своём файле;
    имя файла — путь в проекте без «claude/», «/» заменены на «_»:
    claude/map/rules/82-выгрузка.md → map_rules_82-выгрузка.md.
    Тексты берутся байт в байт (session_extract.py), иначе сверка бессмысленна.

    --after        проверять «Стало» вместо «Было» (сверка после вливания);
    --allow-nodoc  блок без адреса документа (правка кода и т. п.) — предупреждение,
                   а не ошибка.

Формат входа
    Блок правки начинается заголовком «### П-N. <адрес> §<раздел> …» (##–####).
    Адрес — первый путь в обратных кавычках с «/» (`map/rules/82`, `core/rules/40`,
    `ref/map/11`) или, если таких нет, первый путь без кавычек
    (proposals/both/2026-10-08-шесть-групп-объектов-по-слоям). Файл документа ищется
    по префиксу: map/rules/82 → map_rules_82 + («-», «_», «.» или конец имени).
    Нет файла или нашлось несколько — ошибка блока.

    Внутри блока:
        Было: «<дословная цитата>»
        Было: нет; вставить после «<якорь>»
        Стало: «<новый текст>»          (или «Стало, вариант а: «…»»)
    Цитата — от первой «« после «Было:» (или после «после») до «» в конце строки;
    кавычки-ёлочки внутри цитаты допустимы. Строка не кончается на «» — цитата
    продолжается на следующих строках до строки, которая кончается на «».
    Сравнение — точное, без нормализации. Если точного вхождения нет, отдельно
    сообщается, сколько раз цитата нашлась после нормализации пробелов
    (любая серия пробельных знаков — один пробел) и кавычек («»„“”"'‘’ → ").
    Код в ``` … ``` не разбирается.

Вывод
    Таблица «П-N | документ | раздел | найдено | позиция (строка) | примечание»
    и итог: блоков, цитат, найдено ровно один раз, ошибок.

Коды выхода
    0 — каждая цитата найдена в своём документе ровно один раз;
    1 — есть ошибки: цитата не найдена, найдена больше одного раза, нашлась только
        после нормализации, нет документа, документов несколько, нет цитаты;
    2 — ошибка запуска: нет файла или папки, в предложении нет ни одного блока П-N.
"""
import os
import re
import sys

HEADER_RE = re.compile(r'^#{2,4}\s*(П-[0-9A-Za-zА-Яа-я.\-]+?)\.?\s+(.*)$')
FIELD_RE = re.compile(r'^\s*(?:[-*]\s+)?\**(Было|Стало)([^:«]*?)\**\s*:\s*\**\s*(.*)$')
BACKTICK_RE = re.compile(r'`([^`]+)`')
BARE_PATH_RE = re.compile(r'(?<![\w/`])((?:claude/)?(?:core|map|plan|ref|proposals)/[^\s`,;§]+)')
SECTION_RE = re.compile(r'§\s*([0-9A-Za-zА-Яа-яЁё.\-]+)')
INSERT_RE = re.compile(r'^нет\s*[;,.]?\s*вставить\s+после\s*(.*)$', re.S)

QUOTE_MAP = {c: '"' for c in '«»„“”"\'‘’'}
WS = set(' \t\n\r\f\v        　')


def normalize(text):
    """Пробелы — серией в один пробел, кавычки — в ". Возвращает (строка, индексы исходника)."""
    out, idx = [], []
    prev_ws = False
    for i, ch in enumerate(text):
        if ch in WS:
            if not prev_ws:
                out.append(' ')
                idx.append(i)
            prev_ws = True
            continue
        prev_ws = False
        out.append(QUOTE_MAP.get(ch, ch))
        idx.append(i)
    return ''.join(out), idx


def find_all(hay, needle):
    pos, res = 0, []
    if not needle:
        return res
    while True:
        k = hay.find(needle, pos)
        if k < 0:
            return res
        res.append(k)
        pos = k + 1


def line_of(text, pos):
    return text.count('\n', 0, pos) + 1


def extract_quote(first_rest, more_lines):
    """first_rest — текст после «Было:», more_lines — следующие строки блока.
    Возвращает (цитата|None, сколько строк продолжения съедено, примечание)."""
    k = first_rest.find('«')
    if k < 0:
        return None, 0, 'нет «'
    body_first = first_rest[k + 1:]
    if first_rest.rstrip().endswith('»'):
        end = body_first.rstrip()
        note = '' if end == body_first else ''
        return end[:-1], 0, note
    # многострочная цитата
    parts = [body_first]
    for n, ln in enumerate(more_lines, 1):
        if FIELD_RE.match(ln):
            break
        if ln.rstrip().endswith('»'):
            parts.append(ln.rstrip()[:-1])
            return '\n'.join(parts), n, 'многострочная'
        parts.append(ln)
    # не закрылась: берём до последней » в первой строке
    j = body_first.rfind('»')
    if j >= 0:
        return body_first[:j], 0, 'после «» есть текст: ' + body_first[j + 1:].strip()[:40]
    return None, 0, 'цитата не закрыта «»'


def parse_proposal(text):
    blocks = []
    cur = None
    lines = text.split('\n')
    in_fence = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.lstrip().startswith('```'):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        m = HEADER_RE.match(ln)
        if m:
            cur = {'id': m.group(1), 'header': m.group(2), 'line': i + 1, 'fields': []}
            blocks.append(cur)
            i += 1
            continue
        if ln.startswith('#'):
            cur = None
        if cur is not None:
            f = FIELD_RE.match(ln)
            if f:
                quote, eaten, note = extract_quote(f.group(3), lines[i + 1:])
                cur['fields'].append({'kind': f.group(1), 'label': (f.group(1) + f.group(2)).strip(),
                                      'raw': f.group(3), 'quote': quote, 'note': note,
                                      'line': i + 1})
                i += 1 + eaten
                continue
        i += 1
    return blocks


def header_address(header):
    for t in BACKTICK_RE.findall(header):
        t = t.strip()
        if '/' in t and not t.endswith('.py'):
            return t
    m = BARE_PATH_RE.search(header)
    return m.group(1) if m else None


def header_section(header):
    m = SECTION_RE.search(header)
    return m.group(1).rstrip('.,') if m else '—'


def resolve_doc(addr, docs_dir):
    a = addr.strip()
    if a.startswith('claude/'):
        a = a[len('claude/'):]
    if a.endswith('.md'):
        a = a[:-3]
    prefix = a.replace('/', '_')
    hits = []
    for name in sorted(os.listdir(docs_dir)):
        if not name.endswith('.md'):
            continue
        stem = name[:-3]
        if stem == prefix or (stem.startswith(prefix) and stem[len(prefix)] in '-_.'):
            hits.append(name)
    return hits


def count_in(doc_text, quote):
    exact = find_all(doc_text, quote)
    if exact:
        return exact, []
    nd, nidx = normalize(doc_text)
    nq, _ = normalize(quote)
    nq = nq.strip()
    norm = [nidx[k] for k in find_all(nd, nq)] if nq else []
    return [], norm


def check(proposal_path, docs_dir, after=False, allow_nodoc=False):
    with open(proposal_path, encoding='utf-8', newline='') as fh:
        text = fh.read()
    blocks = parse_proposal(text)
    rows, errors, ok, quotes = [], 0, 0, 0
    cache = {}
    for b in blocks:
        addr = header_address(b['header'])
        sect = header_section(b['header'])
        want = 'Стало' if after else 'Было'
        fields = [f for f in b['fields'] if f['kind'] == want]
        if addr is None:
            msg = 'нет адреса документа в заголовке'
            if allow_nodoc:
                rows.append((b['id'], '—', sect, '—', '—', 'пропуск: ' + msg))
            else:
                errors += 1
                rows.append((b['id'], '—', sect, 'ОШИБКА', '—', msg))
            continue
        hits = resolve_doc(addr, docs_dir)
        if len(hits) != 1:
            errors += 1
            msg = 'нет файла документа' if not hits else 'несколько файлов: ' + ', '.join(hits)
            rows.append((b['id'], addr, sect, 'ОШИБКА', '—', msg))
            continue
        doc = hits[0]
        if doc not in cache:
            with open(os.path.join(docs_dir, doc), encoding='utf-8', newline='') as fh:
                cache[doc] = fh.read()
        dtext = cache[doc]
        if not fields:
            errors += 1
            rows.append((b['id'], doc, sect, 'ОШИБКА', '—', 'нет строки «%s:»' % want))
            continue
        for f in fields:
            pid = b['id'] if f['label'] == want else '%s (%s)' % (b['id'], f['label'])
            raw = f['raw'].strip()
            quote, kind_note = f['quote'], ''
            if not after:
                mi = INSERT_RE.match(raw)
                if mi:
                    q, _, n2 = extract_quote(mi.group(1), [])
                    quote, kind_note = q, 'якорь «вставить после»'
                elif raw.startswith('нет'):
                    errors += 1
                    rows.append((pid, doc, sect, 'ОШИБКА', '—', '«нет» без якоря «вставить после «…»»'))
                    continue
            if quote is None:
                errors += 1
                rows.append((pid, doc, sect, 'ОШИБКА', '—', 'цитата не разобрана: ' + (f['note'] or raw[:40])))
                continue
            quotes += 1
            exact, norm = count_in(dtext, quote)
            notes = [n for n in (kind_note, f['note']) if n]
            if exact:
                pos = ', '.join(str(line_of(dtext, p)) for p in exact)
                if len(exact) == 1:
                    ok += 1
                    status = '1'
                else:
                    errors += 1
                    status = '%d — ОШИБКА' % len(exact)
                    notes.append('цитата не единственная')
            else:
                errors += 1
                if norm:
                    status = '0 (норм.: %d) — ОШИБКА' % len(norm)
                    pos = ', '.join(str(line_of(dtext, p)) for p in norm)
                    notes.append('нашлась только после нормализации пробелов и кавычек')
                else:
                    status = '0 — ОШИБКА'
                    pos = '—'
            rows.append((pid, doc, sect, status, pos, '; '.join(notes)))
    return blocks, rows, errors, ok, quotes


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    flags = {a for a in argv if a.startswith('--')}
    unknown = flags - {'--after', '--allow-nodoc'}
    if len(args) != 2 or unknown or '-h' in argv:
        print(__doc__)
        return 2
    prop, docs = args
    if not os.path.isfile(prop) or not os.path.isdir(docs):
        print('нет файла предложения или папки документов', file=sys.stderr)
        return 2
    blocks, rows, errors, ok, quotes = check(prop, docs, '--after' in flags, '--allow-nodoc' in flags)
    if not blocks:
        print('в предложении нет блоков «### П-N.»', file=sys.stderr)
        return 2
    what = 'Стало' if '--after' in flags else 'Было'
    print('# Сверка цитат «%s»: %s' % (what, os.path.basename(prop)))
    print()
    print('| П-N | документ | раздел | найдено | позиция (строка) | примечание |')
    print('|---|---|---|---|---|---|')
    for r in rows:
        print('| ' + ' | '.join(str(c).replace('|', '\\|') for c in r) + ' |')
    print()
    print('Итог: блоков %d, цитат %d, ровно один раз %d, ошибок %d — %s'
          % (len(blocks), quotes, ok, errors, 'ГОТОВО' if errors == 0 else 'ЕСТЬ ОШИБКИ'))
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
