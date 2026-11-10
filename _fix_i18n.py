# -*- coding: utf-8 -*-
"""Naprawia brakujące przecinki po _tr(...) w baza_skryptow.py.

Uszkodzenie: codemod AST wstawił _tr(...) wokół literałów, ale end_col_offset
jest w bajtach UTF-8 — dla linii z znakami nie-ASCII obsunięło się o kilka
znaków i przecinek/przecinek+spacja wylądował WEWNĄTRZ _tr(...), a brakuje go
między argumentami wywołania.
"""
import io
import re
import ast
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PATH = 'baza_skryptow.py'

LIT = r'("(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\')'
# A: _tr(LIT ,? ) <białe znaki> <kolejny literał/f-string> → brak przecinka
PAT_A = re.compile(
    r'(_tr\(\s*' + LIT + r'\s*,?\s*\))([ \t]*(?:\n[ \t]*)?)'
    r'(?=(?:[fFrRbBuU]{1,2})?["\'])')
# B: _tr(LIT ,? ) <spacje> <identifier/keyword-arg> → brak przecinka
#    (wykluczone słowa kluczowe, żeby nie ruszyć ternary/operatorów)
_KW = (r'(?!(?:if|else|for|while|and|or|not|in|is|lambda|return|yield|assert|'
       r'del|pass|break|continue|global|nonlocal|with|as|try|except|finally|'
       r'raise|import|from|class|def|async|await)\b)')
PAT_B = re.compile(
    r'(_tr\(\s*' + LIT + r'\s*,?\s*\))[ \t]*(?=' + _KW + r'[A-Za-z_])')
# C: ')\n)<spacje><instrukcja>' — osierocony nawias wywołania w kolumnie 0
PAT_C = re.compile(r'("\))\n([ \t]*)\)([ \t]+)')


def main():
    for it in range(60):
        src = io.open(PATH, encoding='utf-8').read()
        new, na = PAT_A.subn(lambda m: '_tr(' + m.group(2) + '),' + m.group(3), src)
        new, nb = PAT_B.subn(lambda m: '_tr(' + m.group(2) + '), ', new)
        new, nc = PAT_C.subn(lambda m: m.group(1) + ')\n' + m.group(2) + m.group(3), new)
        # PAT_C: '\1)' to '\")' + ')' = '\"))'; group(2) to wcięcia po ')'
        if new != src:
            io.open(PATH, 'w', encoding='utf-8', newline='').write(new)
            print(f'iter {it}: A={na} B={nb} C={nc}')
        try:
            ast.parse(new)
            print('SYNTAX OK')
            return
        except SyntaxError as e:
            print(f'ERR {e.lineno}: {e.msg}')
            lines = new.splitlines()
            for i in range(max(0, e.lineno - 3), min(len(lines), e.lineno + 2)):
                print(i + 1, lines[i])
            return


if __name__ == '__main__':
    main()
