#!/usr/bin/env python3
"""Проверки quote_check.py на синтетических примерах. Запуск: python3 -I test_quote_check.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quote_check as qc  # noqa: E402

DOC = (
    "# Выгрузка\n"
    "\n"
    "## 1. Формат\n"
    "- **Длинная сторона — не больше 10 000 px.** Экспорт 3×–4×.\n"
    "- Повтор: маска.\n"
    "- Повтор: маска.\n"
    "- Владелец сказал «инженерное» — так и рисуем.\n"
    "- Двойной  пробел и «ёлочки» здесь.\n"
)


class QuoteCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.docs = os.path.join(self.tmp.name, 'docs')
        os.mkdir(self.docs)
        with open(os.path.join(self.docs, 'map_rules_82-выгрузка.md'), 'w', encoding='utf-8') as fh:
            fh.write(DOC)
        # соседний файл с похожим номером — не должен совпасть с map/rules/8
        with open(os.path.join(self.docs, 'map_rules_80-приёмка.md'), 'w', encoding='utf-8') as fh:
            fh.write('# Приёмка\n')

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, body, **kw):
        p = os.path.join(self.tmp.name, 'prop.md')
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write('Черновик\n\n## Правки\n\n' + body)
        return qc.check(p, self.docs, **kw)

    def test_found_once(self):
        _, rows, err, ok, _ = self.run_check(
            "### П-1. `map/rules/82` §1\n"
            "Было: «**Длинная сторона — не больше 10 000 px.** Экспорт 3×–4×.»\n"
            "Стало: «новое»\n")
        self.assertEqual((err, ok), (0, 1))
        self.assertEqual(rows[0][3], '1')
        self.assertEqual(rows[0][4], '4')

    def test_not_found(self):
        _, rows, err, ok, _ = self.run_check(
            "### П-1. `map/rules/82` §1\nБыло: «такого текста нет»\nСтало: «x»\n")
        self.assertEqual((err, ok), (1, 0))
        self.assertTrue(rows[0][3].startswith('0'))

    def test_found_twice(self):
        _, rows, err, _, _ = self.run_check(
            "### П-1. `map/rules/82` §1\nБыло: «- Повтор: маска.»\nСтало: «x»\n")
        self.assertEqual(err, 1)
        self.assertTrue(rows[0][3].startswith('2'))
        self.assertEqual(rows[0][4], '5, 6')

    def test_insert_after_anchor(self):
        _, rows, err, ok, _ = self.run_check(
            "### П-2. `map/rules/82` §1 — после п. «Длинная…»\n"
            "Было: нет; вставить после «Экспорт 3×–4×.»\n"
            "Стало: «- новый пункт»\n")
        self.assertEqual((err, ok), (0, 1))
        self.assertIn('якорь', rows[0][5])

    def test_inner_guillemets(self):
        _, rows, err, ok, _ = self.run_check(
            "### П-3. `map/rules/82` §1\n"
            "Было: нет; вставить после «Владелец сказал «инженерное»»\n"
            "Стало: «; признак»\n")
        self.assertEqual((err, ok), (0, 1))
        self.assertEqual(rows[0][4], '7')

    def test_whitespace_normalized_only(self):
        _, rows, err, ok, _ = self.run_check(
            "### П-4. `map/rules/82` §1\nБыло: «Двойной пробел и \"ёлочки\" здесь.»\nСтало: «x»\n")
        self.assertEqual((err, ok), (1, 0))
        self.assertIn('норм.: 1', rows[0][3])
        self.assertIn('нормализации', rows[0][5])

    def test_address_errors(self):
        _, rows, err, _, _ = self.run_check(
            "### П-5. `map/rules/8` §1\nБыло: «x»\nСтало: «y»\n"
            "### П-6. `unspot_map.to_png` — код\nБыло: «x»\nСтало: «y»\n")
        self.assertEqual(err, 2)
        self.assertIn('нет файла', rows[0][5])
        self.assertIn('нет адреса', rows[1][5])


if __name__ == '__main__':
    unittest.main(verbosity=2)
