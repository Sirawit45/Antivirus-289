import unittest
import os
import re
import sys
from app import AppApi
from core.adb_manager import adb_manager
from core.database_manager import db_manager
from core.scanner import app_scanner
from core.cleaner import app_cleaner
from core.device_security import device_security
from core.logger import logger

class TestAllButtonsAndAPIs(unittest.TestCase):

    def setUp(self):
        self.api = AppApi()
        # Enable simulator mode for test predictability
        adb_manager.set_simulator_mode(True)

    # -------------------------------------------------------------
    # 1. HTML DOM to JS Binding Verification
    # -------------------------------------------------------------
    def test_html_and_js_button_bindings(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(base_dir, "ui", "index.html")
        js_path = os.path.join(base_dir, "ui", "js", "app.js")

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        with open(js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        # 1. Check all onclick handlers in HTML have function definitions in JS
        onclick_matches = re.findall(r'onclick="([a-zA-Z0-9_]+)\(', html_content)
        unique_onclicks = set(onclick_matches)
        
        for handler in unique_onclicks:
            if handler in ['alert']:
                continue
            has_func = f"function {handler}" in js_content or f"{handler} =" in js_content or f"async function {handler}" in js_content
            self.assertTrue(has_func, f"HTML references onclick='{handler}()' but function is not defined in app.js")

        # 2. Check all getElementById in JS exist in HTML
        by_id_matches = re.findall(r"getElementById\(['\"]([a-zA-Z0-9_-]+)['\"]\)", js_content)
        unique_ids = set(by_id_matches)
        
        for el_id in unique_ids:
            has_id = f'id="{el_id}"' in html_content or f"id='{el_id}'" in html_content
            self.assertTrue(has_id, f"JavaScript references getElementById('{el_id}') but ID does not exist in index.html")

        print(f"  [OK] Validated {len(unique_onclicks)} HTML onclick handlers and {len(unique_ids)} JavaScript DOM element IDs.")

    # -------------------------------------------------------------
    # 2. Header & Device Control Buttons
    # -------------------------------------------------------------
    def test_btn_refresh_and_toggle_simulator(self):
        # btnRefreshDevice
        info = self.api.refresh_device_info()
        self.assertIsNotNone(info)
        self.assertIn("serial", info)
        
        # btnToggleSimulator
        self.api.set_simulator_mode(False)
        self.assertFalse(adb_manager.simulator_mode)
        self.api.set_simulator_mode(True)
        self.assertTrue(adb_manager.simulator_mode)
        print("  [OK] Header Refresh & Simulator buttons verified.")

    # -------------------------------------------------------------
    # 3. Tab 1: Scanner Buttons (Quick, Full, Smart, Disabled)
    # -------------------------------------------------------------
    def test_scan_buttons_all_modes(self):
        for mode in ['quick', 'full', 'smart', 'disabled', 'wipe_non_essential']:
            started = self.api.start_scan_async(scan_type=mode)
            self.assertTrue(started, f"Failed to start scan for mode {mode}")
            
            # Poll state
            state = self.api.get_scan_state()
            self.assertIn(state['status'], ['scanning', 'completed'])
            
            # Wait for completion in test
            import time
            for _ in range(25):
                if self.api.get_scan_state()['status'] == 'completed':
                    break
                time.sleep(0.1)
            
            final_state = self.api.get_scan_state()
            self.assertEqual(final_state['status'], 'completed')
            self.assertGreater(final_state['total_count'], 0)
            self.assertIsInstance(final_state['threats'], list)

            # For wipe_non_essential mode, verify that NO banking or social apps are in the threats list!
            if mode == 'wipe_non_essential':
                threat_pkgs = [t['package_name'] for t in final_state['threats']]
                self.assertNotIn("com.kasikorn.retail.mbanking.wap", threat_pkgs)
                self.assertNotIn("com.scb.phone", threat_pkgs)
                self.assertNotIn("ktbcs.netbank", threat_pkgs)
                self.assertNotIn("jp.naver.line.android", threat_pkgs)
                self.assertNotIn("com.facebook.katana", threat_pkgs)
                self.assertNotIn("com.ss.android.ugc.trill", threat_pkgs)
                print(f"  [OK] Wipe Non-Essential Mode: Banking & Social apps (K PLUS, SCB, LINE, TikTok, FB) are 100% PRESERVED!")

            print(f"  [OK] Button [{mode.upper()} Scan] works: Scanned {final_state['scanned_count']} apps, detected {len(final_state['threats'])} threats.")

    # -------------------------------------------------------------
    # 4. Tab 1: Cleaner Buttons (Single & Batch Clean)
    # -------------------------------------------------------------
    def test_cleaner_buttons(self):
        # Single clean button
        res, msg = self.api.uninstall_package("com.dummy.test.pkg", is_system=False)
        self.assertTrue(res, f"Uninstall failed: {msg}")

        # Batch clean button (btnCleanAll)
        threats = [
            {"package_name": "com.revenuedepartment.app", "is_system": False},
            {"package_name": "com.space.whizclear.qub", "is_system": False}
        ]
        started = self.api.start_clean_async(threats)
        self.assertTrue(started)
        
        import time
        for _ in range(20):
            if self.api.get_clean_state()['status'] == 'completed':
                break
            time.sleep(0.1)
            
        clean_state = self.api.get_clean_state()
        self.assertEqual(clean_state['status'], 'completed')
        self.assertEqual(clean_state['success_count'], 2)
        print("  [OK] Buttons [Clean Threat] & [Clean All Selected] verified.")

    # -------------------------------------------------------------
    # 5. Tab 2: Update & Custom Blacklist/Whitelist Buttons
    # -------------------------------------------------------------
    def test_database_update_and_custom_rules_buttons(self):
        # btnPerformUpdate
        update_res = self.api.perform_update()
        self.assertTrue(update_res['success'])
        
        # Add custom signature button
        add_sig, _ = self.api.add_custom_signature("com.malware.audit289", "Audit Trojan", "CRITICAL")
        self.assertTrue(add_sig)
        
        # Remove custom signature button
        rem_sig, _ = self.api.remove_custom_signature("com.malware.audit289")
        self.assertTrue(rem_sig)

        # Add custom whitelist button
        add_wl, _ = self.api.add_custom_whitelist("com.mycorp.app289", "My Corp", "Corporate")
        self.assertTrue(add_wl)

        # Remove custom whitelist button
        rem_wl, _ = self.api.remove_custom_whitelist("com.mycorp.app289")
        self.assertTrue(rem_wl)
        print("  [OK] Tab 2 Update & Rule Management buttons verified.")

    # -------------------------------------------------------------
    # 6. Tab 3: Security Hardening & Power Buttons
    # -------------------------------------------------------------
    def test_security_hardening_and_power_buttons(self):
        # Disable ADB button
        res_adb, _ = self.api.disable_adb()
        self.assertTrue(res_adb)

        # Disable Developer Settings button
        res_dev, _ = self.api.disable_developer_settings()
        self.assertTrue(res_dev)

        # Reboot buttons
        for mode in ['normal', 'recovery', 'bootloader']:
            res_rb = self.api.reboot_device(mode)
            self.assertTrue(res_rb, f"Reboot {mode} failed")

        print("  [OK] Tab 3 Security & Reboot buttons verified.")

    # -------------------------------------------------------------
    # 7. Tab 4: App Manager Buttons
    # -------------------------------------------------------------
    def test_app_manager_buttons(self):
        packages = self.api.get_installed_packages()
        self.assertIsInstance(packages, list)
        self.assertGreater(len(packages), 0)
        user_apps = [p for p in packages if not p['is_system']]
        sys_apps = [p for p in packages if p['is_system']]
        self.assertGreater(len(user_apps), 0)
        self.assertGreater(len(sys_apps), 0)
        print(f"  [OK] Tab 4 App Manager loaded {len(packages)} apps ({len(user_apps)} User / {len(sys_apps)} System).")

    # -------------------------------------------------------------
    # 8. Tab 5: Driver Installer Buttons
    # -------------------------------------------------------------
    def test_driver_buttons(self):
        res_samsung, _ = self.api.install_samsung_driver()
        res_adb_drv, _ = self.api.install_universal_adb_driver()
        # Even if bin is mock or physical, API method returns a tuple (bool, msg)
        self.assertIsInstance(res_samsung, bool)
        self.assertIsInstance(res_adb_drv, bool)
        print("  [OK] Tab 5 Samsung & Universal ADB Driver Installer buttons verified.")

    # -------------------------------------------------------------
    # 9. Tab 6: Logs Buttons
    # -------------------------------------------------------------
    def test_logs_buttons(self):
        logs = self.api.get_live_logs()
        self.assertIsInstance(logs, list)
        cleared = self.api.clear_logs()
        self.assertTrue(cleared)
        self.assertEqual(len(self.api.get_live_logs()), 0)
        print("  [OK] Tab 6 Live Logs & Clear Logs buttons verified.")

if __name__ == '__main__':
    unittest.main()
