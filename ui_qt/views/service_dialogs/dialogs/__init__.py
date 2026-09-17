"""Per-dialog modules for the service dialogs (V18.20.4.6, P5 / O-b2).

Split out of ui_qt/views/service_dialogs/base_dialog.py — one module
per dialog + shared.py for the cross-dialog plumbing. Docstring only:
importing the dialog classes still goes through
ui_qt.views.service_dialogs.base_dialog (back-compat facade) or the
individual modules.
"""
