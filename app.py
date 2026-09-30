import os
import sys
import webview
import threading
from core import get_base_dir
from core.logger import logger
from core.adb_manager import adb_manager
from core.database_manager import db_manager
from core.scanner import app_scanner
from core.cleaner import app_cleaner
from core.device_security import device_security

class AppApi:
    """Clean Stateless JavaScript Bridge API (No circular .NET objects)"""

    # --- Device & ADB ---
    def get_device_info(self):
        return adb_manager.device_info or None

    def refresh_device_info(self):
        return adb_manager.refresh_device_info()

    def set_simulator_mode(self, enabled):
        adb_manager.set_simulator_mode(enabled)
        return True

    # --- Database & Updates ---
    def get_database_stats(self):
        return db_manager.get_stats()

    def check_for_updates(self):
        return db_manager.check_for_updates()

    def perform_update(self):
        return db_manager.perform_update()

    def add_custom_signature(self, pkg, name, risk="HIGH"):
        return db_manager.add_custom_signature(pkg, name, risk)

    def remove_custom_signature(self, pkg):
        return db_manager.remove_custom_signature(pkg)

    def add_custom_whitelist(self, pkg, name, cat="Custom"):
        return db_manager.add_custom_whitelist(pkg, name, cat)

    def remove_custom_whitelist(self, pkg):
        return db_manager.remove_custom_whitelist(pkg)

    # --- Async Scanner ---
    def start_scan_async(self, scan_type="quick"):
        return app_scanner.start_scan_async(scan_type=scan_type)

    def get_scan_state(self):
        return app_scanner.get_state()

    def cancel_scan(self):
        app_scanner.cancel_scan()
        return True

    # --- Async Cleaner ---
    def uninstall_package(self, pkg, is_system=False):
        return app_cleaner.uninstall_package(pkg, is_system=is_system)

    def start_clean_async(self, threat_list):
        return app_cleaner.start_clean_async(threat_list)

    def get_clean_state(self):
        return app_cleaner.get_state()

    def cancel_cleaning(self):
        app_cleaner.cancel_cleaning()
        return True

    # --- Device Security Hardening ---
    def disable_adb(self):
        return device_security.disable_adb()

    def disable_developer_settings(self):
        return device_security.disable_developer_settings()

    def reboot_device(self, mode="normal"):
        return device_security.reboot(mode)

    def install_samsung_driver(self):
        return device_security.install_samsung_driver()

    def install_universal_adb_driver(self):
        return device_security.install_universal_adb_driver()

    # --- App Manager ---
    def get_installed_packages(self):
        dev_serial = adb_manager.connected_device or ("SIMULATOR-289-VIP" if adb_manager.simulator_mode else None)
        if not dev_serial:
            return []

        user_pkgs = app_scanner._get_packages(dev_serial, "-3")
        sys_pkgs = app_scanner._get_packages(dev_serial, "-s")
        dis_pkgs = app_scanner._get_packages(dev_serial, "-d")

        all_items = []
        for p in user_pkgs:
            is_ess, name, cat = db_manager.is_banking_or_social(p)
            all_items.append({
                "package_name": p, 
                "is_system": False, 
                "is_disabled": p in dis_pkgs,
                "is_essential": is_ess,
                "essential_category": cat
            })
        for p in sys_pkgs:
            all_items.append({"package_name": p, "is_system": True, "is_disabled": p in dis_pkgs, "is_essential": True})
        for p in dis_pkgs:
            if not any(x["package_name"] == p for x in all_items):
                is_ess, name, cat = db_manager.is_banking_or_social(p)
                all_items.append({
                    "package_name": p, 
                    "is_system": False, 
                    "is_disabled": True,
                    "is_essential": is_ess,
                    "essential_category": cat
                })
        return all_items

    # --- Logs ---
    def get_live_logs(self):
        return logger.get_history()

    def clear_logs(self):
        logger.clear()
        return True

def main():
    base_dir = get_base_dir()
    html_path = os.path.join(base_dir, "ui", "index.html")
    if not os.path.exists(html_path):
        from core import get_app_dir
        html_path = os.path.join(get_app_dir(), "ui", "index.html")

    # Start background ADB monitoring
    adb_manager.start_monitoring(poll_interval=3.0)

    # Initialize clean stateless bridge API
    api = AppApi()

    logger.info("Initializing APKs Guard Pro 289 Engine...", "กำลังเริ่มต้นระบบความปลอดภัย...")

    # Create PyWebView window (No cmd window needed!)
    window = webview.create_window(
        title="APKs Guard Pro 289 - Android Antivirus & Threat Neutralizer",
        url=html_path,
        js_api=api,
        width=1220,
        height=800,
        min_size=(980, 620),
        background_color='#f4f6f9'
    )

    try:
        webview.start(debug=False)
    finally:
        adb_manager.stop_monitoring()

if __name__ == '__main__':
    main()
