# your_app/setup.py
import frappe

def after_install():
    """Runs after app is installed"""
    run_patches()

def after_migrate():
    """Runs after app is updated/migrated"""
    run_patches()

def run_patches():
    """Execute all pending patches"""
    from frappe.modules.patch_handler import run_all
    run_all(skip_failing=False)