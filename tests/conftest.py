import pytest

def pytest_configure(config):
    """
    Globale Konfiguration für pytest, um die Ausgabe sauber zu halten.
    """
    config.option.tbstyle = 'short'
    config.option.log_level = 'ERROR'
    config.option.log_cli_level = 'ERROR'
