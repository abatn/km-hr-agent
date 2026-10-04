# Wichtig: NiceGUI user_simulation erwartet ein Projekt-Root mit ini-Datei
# (nicegui/testing/general_fixtures.py:40 verlangt config.inipath).
# pytest_plugins muss in der ROOT-conftest.py stehen (pytest 8+).
pytest_plugins = ["nicegui.testing.user_plugin"]
