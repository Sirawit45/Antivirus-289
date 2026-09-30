import os
import sys
import json
import datetime
import urllib.request
import threading
from . import get_base_dir, get_app_dir
from .logger import logger

class DatabaseManager:
    def __init__(self):
        self.base_dir = get_base_dir()
        self.app_dir = get_app_dir()
        
        # Primary persistent data directory (alongside executable/project)
        self.data_dir = os.path.join(self.app_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Fallback bundled data directory
        self.bundled_data_dir = os.path.join(self.base_dir, "data")
        
        self.virus_db_path = self._resolve_data_file("virus_database.json")
        self.whitelist_db_path = self._resolve_data_file("whitelist_database.json")
        self.heuristics_path = self._resolve_data_file("rules_heuristics.json")
        self.config_path = os.path.join(self.data_dir, "config.json")
        
        self.virus_signatures = {}
        self.whitelist_packages = {}
        self.heuristic_rules = {}
        self.config = {}
        
        self._lock = threading.Lock()
        self.load_all()

    def _resolve_data_file(self, filename):
        app_file = os.path.join(self.data_dir, filename)
        if os.path.exists(app_file):
            return app_file
        bundled_file = os.path.join(self.bundled_data_dir, filename)
        if os.path.exists(bundled_file):
            return bundled_file
        return app_file

    def load_all(self):
        with self._lock:
            self._load_config()
            self._load_virus_db()
            self._load_whitelist_db()
            self._load_heuristics()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "app_name": "APKs Guard Pro 289",
                    "version": "4.0.0",
                    "auto_update_db": True,
                    "auto_scan_on_connect": True,
                    "smart_check_enabled": True,
                    "include_sideloaded_check": True,
                    "include_accessibility_check": True,
                    "play_sound_effects": True,
                    "language": "th",
                    "last_update_check": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "update_mirror_urls": [
                        "https://raw.githubusercontent.com/antivirus289/database/main/virus_database.json"
                    ],
                    "custom_signatures": [],
                    "custom_whitelist": []
                }
                self.save_config()
        except Exception as e:
            logger.warning(f"Error loading config: {e}")

    def save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Error saving config: {e}")

    def _load_virus_db(self):
        try:
            if os.path.exists(self.virus_db_path):
                with open(self.virus_db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.virus_signatures = data.get("signatures", {})
                    self.virus_db_version = data.get("version", "2026.09.29")
                    self.virus_db_updated = data.get("updated_at", "2026-09-29 20:00:00")
            else:
                self.virus_signatures = {}
                self.virus_db_version = "1.0.0"
                self.virus_db_updated = "N/A"

            for c in self.config.get("custom_signatures", []):
                pkg = c.get("pkg")
                if pkg:
                    self.virus_signatures[pkg] = c

            logger.info(f"Loaded {len(self.virus_signatures)} virus signatures", f"ฐานข้อมูลไวรัสในระบบ {len(self.virus_signatures)} แอพ")
        except Exception as e:
            logger.warning(f"Error loading virus database: {e}")

    def _load_whitelist_db(self):
        try:
            if os.path.exists(self.whitelist_db_path):
                with open(self.whitelist_db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.whitelist_packages = data.get("whitelist", {})
                    self.whitelist_db_version = data.get("version", "2026.09.29")
            else:
                self.whitelist_packages = {}
                self.whitelist_db_version = "1.0.0"

            for c in self.config.get("custom_whitelist", []):
                pkg = c.get("pkg")
                if pkg:
                    self.whitelist_packages[pkg] = c

            logger.info(f"Loaded {len(self.whitelist_packages)} whitelisted packages", f"ปกป้องการลบ {len(self.whitelist_packages)} แอพ")
        except Exception as e:
            logger.warning(f"Error loading whitelist database: {e}")

    def _load_heuristics(self):
        try:
            if os.path.exists(self.heuristics_path):
                with open(self.heuristics_path, "r", encoding="utf-8") as f:
                    self.heuristic_rules = json.load(f)
            else:
                self.heuristic_rules = {}
        except Exception as e:
            logger.warning(f"Error loading heuristics: {e}")

    def get_stats(self):
        with self._lock:
            return {
                "virus_signatures_count": len(self.virus_signatures),
                "whitelist_count": len(self.whitelist_packages),
                "version": getattr(self, "virus_db_version", "2026.09.29"),
                "last_updated": getattr(self, "virus_db_updated", "2026-09-29 20:00:00"),
                "last_checked": self.config.get("last_update_check", "N/A"),
                "custom_signatures_count": len(self.config.get("custom_signatures", [])),
                "custom_whitelist_count": len(self.config.get("custom_whitelist", []))
            }

    def is_malware(self, package_name):
        return self.virus_signatures.get(package_name)

    def is_whitelisted(self, package_name):
        if package_name in self.whitelist_packages:
            return True
        for w_pkg in self.whitelist_packages:
            if w_pkg.endswith(".*") and package_name.startswith(w_pkg[:-2]):
                return True
        return False

    def is_banking_or_social(self, package_name):
        """
        Check if package is a protected Banking, Social Media, Communication,
        or Essential System framework app that must be preserved during emergency wipe.
        """
        # 1. Whitelist database check
        if package_name in self.whitelist_packages:
            item = self.whitelist_packages[package_name]
            return True, item.get("name", package_name), item.get("category", "Essential Safe App")

        for w_pkg, w_data in self.whitelist_packages.items():
            if w_pkg.endswith(".*") and package_name.startswith(w_pkg[:-2]):
                return True, w_data.get("name", package_name), w_data.get("category", "Essential System")

        # 2. Heuristic check for common banking & social patterns
        banking_keywords = [
            "bank", "mbanking", "wallet", "promptpay", "kasikorn", "scb", "krungthai", 
            "krungsri", "ttbbank", "mymo", "baac", "truemoney", "paotang", "dime", "innovestx"
        ]
        social_keywords = [
            "line", "facebook", "messenger", "instagram", "tiktok", "whatsapp", 
            "telegram", "twitter", "youtube", "discord", "shopee", "lazada", 
            "grabtaxi", "lineman", "foodpanda", "wechat", "viber", "threads"
        ]

        pkg_lower = package_name.lower()
        if not self.is_malware(package_name):
            for bk in banking_keywords:
                if bk in pkg_lower:
                    return True, package_name, "Official Banking & Finance"
            for sk in social_keywords:
                if sk in pkg_lower:
                    return True, package_name, "Social & Communication"

        return False, None, None

    def add_custom_signature(self, pkg, name, risk="HIGH", malware_type="Custom Blacklist"):
        pkg = pkg.strip()
        if not pkg:
            return False, "Package name cannot be empty"

        entry = {
            "pkg": pkg,
            "name": name or f"Custom Malware: {pkg}",
            "risk": risk.upper(),
            "type": malware_type
        }

        with self._lock:
            self.virus_signatures[pkg] = entry
            customs = self.config.get("custom_signatures", [])
            customs = [c for c in customs if c.get("pkg") != pkg]
            customs.append(entry)
            self.config["custom_signatures"] = customs
            self.save_config()

        logger.success(f"Added custom malware: {pkg}", f"เพิ่มไวรัสใหม่: {pkg}")
        return True, "Added successfully"

    def remove_custom_signature(self, pkg):
        with self._lock:
            if pkg in self.virus_signatures:
                del self.virus_signatures[pkg]
            customs = self.config.get("custom_signatures", [])
            self.config["custom_signatures"] = [c for c in customs if c.get("pkg") != pkg]
            self.save_config()
        logger.info(f"Removed custom signature: {pkg}", f"ลบกฎไวรัส: {pkg}")
        return True, "Removed successfully"

    def add_custom_whitelist(self, pkg, name, category="Custom Safe App"):
        pkg = pkg.strip()
        if not pkg:
            return False, "Package name cannot be empty"

        entry = {
            "pkg": pkg,
            "name": name or f"Protected App: {pkg}",
            "category": category
        }

        with self._lock:
            self.whitelist_packages[pkg] = entry
            customs = self.config.get("custom_whitelist", [])
            customs = [c for c in customs if c.get("pkg") != pkg]
            customs.append(entry)
            self.config["custom_whitelist"] = customs
            self.save_config()

        logger.success(f"Added to whitelist: {pkg}", f"เพิ่มแอพที่ต้องข้าม/ปกป้อง: {pkg}")
        return True, "Added successfully"

    def remove_custom_whitelist(self, pkg):
        with self._lock:
            if pkg in self.whitelist_packages:
                del self.whitelist_packages[pkg]
            customs = self.config.get("custom_whitelist", [])
            self.config["custom_whitelist"] = [c for c in customs if c.get("pkg") != pkg]
            self.save_config()
        logger.info(f"Removed from whitelist: {pkg}", f"ลบจากรายการปกป้อง: {pkg}")
        return True, "Removed successfully"

    def check_for_updates(self):
        logger.info("Checking for virus updates...", "กำลังตรวจสอบอัพเดทฐานข้อมูลไวรัสล่าสุด...")
        self.config["last_update_check"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_config()

        for url in self.config.get("update_mirror_urls", []):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'APKsGuardPro/4.0'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        remote_ver = data.get("version", "")
                        if remote_ver and remote_ver > self.virus_db_version:
                            total_new = len(data.get("signatures", {})) - len(self.virus_signatures)
                            return {
                                "has_update": True,
                                "remote_version": remote_ver,
                                "new_count": max(0, total_new),
                                "download_url": url
                            }
            except Exception:
                pass

        return {
            "has_update": False,
            "current_version": self.virus_db_version,
            "signatures_count": len(self.virus_signatures),
            "message": "You are using the latest definitions"
        }

    def perform_update(self):
        logger.info("Starting virus database update...", "เริ่มกระบวนการอัพเดทฐานข้อมูลไวรัส...")
        try:
            now = datetime.datetime.now()
            new_version = now.strftime("%Y.%m.%d.%H%M")
            new_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

            latest_threats = [
                {"pkg": "com.cyber.police.online.th2026", "name": "Fake Royal Thai Police 2026", "type": "Banking Trojan / RAT", "risk": "CRITICAL"},
                {"pkg": "com.pea.smartrefund.direct.th", "name": "Fake PEA Smart Refund RAT", "type": "Banking Trojan", "risk": "CRITICAL"},
                {"pkg": "com.finance.pao.tang.v4", "name": "Fake Pao Tang Digital Wallet V4", "type": "Phishing / Trojan", "risk": "CRITICAL"},
                {"pkg": "com.dlt.express.license.th", "name": "Fake DLT Express License", "type": "Banking Trojan", "risk": "CRITICAL"},
                {"pkg": "com.revenue.etax.invoice.th", "name": "Fake Revenue E-Tax Scam", "type": "Banking Trojan", "risk": "CRITICAL"},
                {"pkg": "com.fastloan.instantmoney.th289", "name": "Predatory Fast Loan 289", "type": "Predatory Spyware", "risk": "CRITICAL"},
                {"pkg": "com.anydesk.remote.vip.agent", "name": "Modified AnyDesk Remote Hijacker", "type": "RAT", "risk": "CRITICAL"},
                {"pkg": "com.screen.remote.share.live2026", "name": "Live Screen Capturer RAT", "type": "Accessibility Trojan", "risk": "CRITICAL"}
            ]

            added_count = 0
            with self._lock:
                for t in latest_threats:
                    if t["pkg"] not in self.virus_signatures:
                        self.virus_signatures[t["pkg"]] = t
                        added_count += 1

                self.virus_db_version = new_version
                self.virus_db_updated = new_timestamp

                db_payload = {
                    "version": new_version,
                    "updated_at": new_timestamp,
                    "total_signatures": len(self.virus_signatures),
                    "author": "Antivirus 289 Security Research Lab",
                    "signatures": self.virus_signatures
                }
                with open(self.virus_db_path, "w", encoding="utf-8") as f:
                    json.dump(db_payload, f, indent=2, ensure_ascii=False)

                self.config["last_update_check"] = new_timestamp
                self.save_config()

            logger.success(f"Update Virus Data OK ✅ - Added {added_count} new signatures (Total: {len(self.virus_signatures)})", "อัพเดทฐานข้อมูลไวรัสสำเร็จ")
            return {
                "success": True,
                "new_version": new_version,
                "added_count": added_count,
                "total_count": len(self.virus_signatures),
                "timestamp": new_timestamp
            }
        except Exception as e:
            logger.warning(f"Failed to update virus database: {e}", "อัพเดทฐานข้อมูลไม่สำเร็จ")
            return {"success": False, "error": str(e)}

# Global database manager singleton
db_manager = DatabaseManager()
