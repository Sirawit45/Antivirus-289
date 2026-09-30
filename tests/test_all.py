import os
import sys
import time
import unittest

sys.stdout.reconfigure(encoding='utf-8')

# Add project root to sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from core.logger import logger
from core.adb_manager import adb_manager
from core.database_manager import db_manager
from core.scanner import app_scanner
from core.cleaner import app_cleaner
from core.device_security import device_security
from app import AppApi

class TestAPKsGuardPro289(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n========================================================")
        print("   STARTING FULL SYSTEM TEST FOR APKs GUARD PRO 289     ")
        print("========================================================")
        adb_manager.set_simulator_mode(True)

    def test_01_database_integrity(self):
        print("\n[TEST 1] Testing Database Integrity & Stats...")
        stats = db_manager.get_stats()
        self.assertGreater(stats["virus_signatures_count"], 2000)
        self.assertGreater(stats["whitelist_count"], 100)
        print(f"  [OK] Total Virus Signatures: {stats['virus_signatures_count']}")
        print(f"  [OK] Total Whitelisted Apps: {stats['whitelist_count']}")
        print(f"  [OK] Database Version: {stats['version']}")

    def test_02_whitelist_protection(self):
        print("\n[TEST 2] Testing Whitelist Protection...")
        safe_apps = [
            "com.kasikorn.retail.mbanking.wap",
            "com.scb.phone",
            "jp.naver.line.android",
            "com.facebook.katana",
            "com.google.android.gms"
        ]
        for app in safe_apps:
            self.assertTrue(db_manager.is_whitelisted(app))
            print(f"  [OK] Protected: {app}")

    def test_03_custom_rule_management(self):
        print("\n[TEST 3] Testing Custom Rule Add/Remove...")
        test_pkg = "com.test.newscam2026.app"
        ok, msg = db_manager.add_custom_signature(test_pkg, "Test Scam 2026", "CRITICAL", "Banking Trojan")
        self.assertTrue(ok)
        self.assertIsNotNone(db_manager.is_malware(test_pkg))
        print(f"  [OK] Added custom rule: {test_pkg}")
        
        ok2, msg2 = db_manager.remove_custom_signature(test_pkg)
        self.assertTrue(ok2)
        print(f"  [OK] Removed custom rule: {test_pkg}")

    def test_04_database_update_system(self):
        print("\n[TEST 4] Testing Virus Definition Update Routine...")
        initial_stats = db_manager.get_stats()
        update_res = db_manager.perform_update()
        self.assertTrue(update_res["success"])
        new_stats = db_manager.get_stats()
        self.assertGreaterEqual(new_stats["virus_signatures_count"], initial_stats["virus_signatures_count"])
        print(f"  [OK] Update successful! New Version: {new_stats['version']}, Total: {new_stats['virus_signatures_count']}")

    def test_05_adb_telemetry(self):
        print("\n[TEST 5] Testing Device Telemetry & ADB Controller...")
        dev_info = adb_manager.refresh_device_info()
        self.assertIsNotNone(dev_info)
        self.assertEqual(dev_info["brand"], "Samsung")
        self.assertIn("Galaxy", dev_info["model"])
        print(f"  [OK] Detected Device: {dev_info['brand']} {dev_info['model']} (Android {dev_info['android_version']})")
        print(f"  [OK] Serial: {dev_info['serial']}, Battery: {dev_info['battery']}")

    def test_06_async_scanner_modes(self):
        print("\n[TEST 6] Testing Asynchronous Scanning Engines...")
        for mode in ["quick", "full", "smart", "disabled"]:
            app_scanner.start_scan_async(scan_type=mode)
            
            # Wait for completion
            for _ in range(50):
                time.sleep(0.05)
                state = app_scanner.get_state()
                if state["status"] in ["completed", "cancelled"]:
                    break
            
            state = app_scanner.get_state()
            self.assertEqual(state["status"], "completed")
            print(f"  [OK] {mode.upper()} Async Scan completed! Inspected {state['scanned_count']} apps, Found {len(state['threats'])} threats.")

    def test_07_async_cleaner_engine(self):
        print("\n[TEST 7] Testing Asynchronous Cleaner Engine...")
        threats_to_clean = [
            {"package_name": "com.revenuedepartment.app", "is_system": False},
            {"package_name": "borrorhealthcare.store", "is_system": False}
        ]
        app_cleaner.start_clean_async(threats_to_clean)
        
        for _ in range(50):
            time.sleep(0.05)
            state = app_cleaner.get_state()
            if state["status"] in ["completed", "cancelled"]:
                break

        state = app_cleaner.get_state()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["success_count"], 2)
        print(f"  [OK] Successfully cleaned {state['success_count']} malware packages asynchronously.")

    def test_08_device_security_hardening(self):
        print("\n[TEST 8] Testing Device Security Hardening...")
        ok1, msg1 = device_security.disable_adb()
        self.assertTrue(ok1)
        print(f"  [OK] Disable ADB: {msg1}")

        ok2, msg2 = device_security.disable_developer_settings()
        self.assertTrue(ok2)
        print(f"  [OK] Disable Dev Options: {msg2}")

    def test_09_api_bridge(self):
        print("\n[TEST 9] Testing Frontend Bridge API (AppApi)...")
        api = AppApi()
        stats = api.get_database_stats()
        self.assertIsNotNone(stats)
        logs = api.get_live_logs()
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)
        print(f"  [OK] API Bridge validated ({len(logs)} log history events recorded).")

if __name__ == '__main__':
    unittest.main(verbosity=2)
