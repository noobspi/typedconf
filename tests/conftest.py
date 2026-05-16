import pytest

def pytest_configure(config):
    """
    Globale Konfiguration für pytest, um die Ausgabe sauber zu halten.
    """
    # Setzt den Traceback-Stil auf 'short', damit nur die relevante Zeile 
    # des Tests und der Fehler angezeigt werden, nicht der volle Pydantic-Stack.
    config.option.tbstyle = 'short'

    # Unterdrückt Log-Output bei erfolgreichen Tests.
    # Logs werden nur bei Fehlern angezeigt.
    config.option.log_level = 'WARNING'
    config.option.log_cli_level = 'WARNING'
    