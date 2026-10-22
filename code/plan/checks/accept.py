# Accepting a stop of the gates (code 007; plan/rules/60 §8, owner's decision of 04.10.2026, строка 164): the reason of an
#   accepted stop - `why` of cfg.GATE_ACCEPT, cfg.GATE7_ACCEPT, cfg.GATE_PLACES - is one of four kinds, each with its link:
#     ложная остановка        - a proposal to fix the check:      proposals/...
#     решение владельца       - a row of the owner's register:    "строка NNN" or ref/core/10
#     открытый вопрос         - the question:                     core/rules/20, "вопрос N" / "№ N" or a picture questions/....png
#     так в исходнике         - a frame of the place:             a picture file name, ....png / .jpg
#   A why without a kind, or with a kind and no link of that kind, accepts nothing: the stop stays (stand of 06.10.2026).
import re
KINDS = [
    ('ложная остановка', r'ложн\w*\s+остановк', r'proposals/\S+'),
    ('решение владельца', r'решени\w*\s+владельц', r'строк\w*\s*№?\s*\d+|ref/core/10'),
    ('открытый вопрос', r'открыт\w*\s+вопрос|вопрос\w*\s+владельц', r'core/rules/20|вопрос\w*\s*№?\s*\d+|№\s*\d+|questions/\S+\.(png|jpe?g)'),
    ('так в исходнике', r'(так|как)\s+(нарисован\w*\s+)?в\s+исходник|по\s+исходнику', r'\S+\.(png|jpe?g)\b'),
]
NONE_SAID = r'причин\w*\s+(из\s+закрытого\s+списка\s+)?нет|нет\s+причин|без\s+причин'
def why_kind(why):
    """(kind, '') when the reason names a kind of the closed list and gives that kind's link; (None, what is missing) else.
    A why that says itself that some of its places have no reason of the list ('причины из закрытого списка нет') accepts
    nothing: one acceptance covers all its places (floor 4: S5s, 6 places by the owner's decision and 7 without a reason)"""
    w = (why or '').strip()
    if not w: return None, 'причина пуста'
    if re.search(NONE_SAID, w, re.I): return None, 'в причине сказано, что у части мест причины из закрытого списка нет'
    named = [(k, link) for k, kre, link in KINDS if re.search(kre, w, re.I)]
    if not named: return None, 'нет вида причины из закрытого списка (ложная остановка, решение владельца, открытый вопрос, так в исходнике)'
    for k, link in named:
        if re.search(link, w, re.I): return k, ''
    return None, f'вид «{named[0][0]}» без ссылки: ' + {'ложная остановка': 'предложение в proposals/',
                                                         'решение владельца': 'строка реестра ref/core/10',
                                                         'открытый вопрос': 'номер вопроса core/rules/20 или картинка questions/…png',
                                                         'так в исходнике': 'кадр места …png'}[named[0][0]]
