"""Geteilter Zustand für R5-5 Dialog-Tests.

Warum ein eigenes Modul: user_simulation führt tests/nicegui_main.py je Test
via runpy FRISCH aus (neues Modul-Objekt), während `import tests.nicegui_main`
im Test das gecachte Modul des ersten Laufs liefert — der zweite Test las
daher die refs der toten App (gemessen: KeyError). Dieses Modul wird von
beiden runpy-Läufen normal importiert und ist damit in sys.modules stabil.
"""
p2_confirm_refs: dict = {}
