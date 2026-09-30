import re
import threading
import time
from .adb_manager import adb_manager
from .database_manager import db_manager
from .logger import logger

class AppScanner:
    def __init__(self):
        self.is_scanning = False
        self._cancel_requested = False
        self.scan_results = []
        self._lock = threading.Lock()
        self.state = {
            "status": "idle",  # "idle", "scanning", "completed", "cancelled"
            "percent": 0,
            "current_package": "",
            "scanned_count": 0,
            "total_count": 0,
            "threats_count": 0,
            "threats": [],
            "summary": {
                "total_scanned": 0,
                "threats_found": 0,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "skipped_count": 0,
                "clean_count": 0,
                "scan_type": "quick"
            }
        }

    def get_state(self):
        with self._lock:
            return dict(self.state)

    def cancel_scan(self):
        with self._lock:
            self._cancel_requested = True
            self.state["status"] = "cancelled"
        logger.warning("Scan cancellation requested by user", "ผู้ใช้ยกเลิกการสแกน")

    def start_scan_async(self, scan_type="quick"):
        """Start scan in background thread"""
        with self._lock:
            if self.is_scanning:
                return False
            self.is_scanning = True
            self._cancel_requested = False
            self.scan_results = []
            self.state = {
                "status": "scanning",
                "percent": 0,
                "current_package": "กำลังเตรียมการสแกน...",
                "scanned_count": 0,
                "total_count": 0,
                "threats_count": 0,
                "threats": [],
                "summary": {
                    "total_scanned": 0,
                    "threats_found": 0,
                    "critical_count": 0,
                    "high_count": 0,
                    "medium_count": 0,
                    "skipped_count": 0,
                    "clean_count": 0,
                    "scan_type": scan_type
                }
            }

        t = threading.Thread(target=self._scan_worker, args=(scan_type,), daemon=True)
        t.start()
        return True

    def _scan_worker(self, scan_type):
        logger.info(f"Starting {scan_type.upper()} scan...", f"เริ่มสแกน ({scan_type})...")

        dev_serial = adb_manager.connected_device or ("SIMULATOR-289-VIP" if adb_manager.simulator_mode else None)
        if not dev_serial:
            logger.warning("No device connected for scanning", "ไม่พบอุปกรณ์ กรุณาเชื่อมต่อ USB Debugging")
            with self._lock:
                self.is_scanning = False
                self.state["status"] = "completed"
                self.state["current_package"] = "ไม่พบอุปกรณ์เชื่อมต่อ"
            return

        # 1. Fetch package lists
        user_packages = self._get_packages(dev_serial, "-3")
        system_packages = self._get_packages(dev_serial, "-s") if scan_type == "full" else []
        disabled_packages = self._get_packages(dev_serial, "-d") if scan_type in ["full", "disabled"] else []

        # 2. Fetch installer sources if smart / full
        installer_map = {}
        if scan_type in ["full", "smart"]:
            logger.info("Starting installer check...", "กำลังเช็คแหล่งที่มาของแอพ...")
            installer_map = self._get_installer_map(dev_serial)
            logger.info("Installer check completed.", "เช็คเสร็จสิ้น")

        # 3. Fetch accessibility services
        accessibility_abusers = set()
        if scan_type in ["full", "smart"]:
            accessibility_abusers = self._get_accessibility_services(dev_serial)

        # Build target list to scan
        targets = []
        for p in user_packages:
            targets.append({"pkg": p, "is_system": False, "is_disabled": p in disabled_packages})

        if scan_type in ["full", "disabled"]:
            for p in disabled_packages:
                if not any(t["pkg"] == p for t in targets):
                    targets.append({"pkg": p, "is_system": False, "is_disabled": True})

        if scan_type == "full":
            for p in system_packages:
                targets.append({"pkg": p, "is_system": True, "is_disabled": p in disabled_packages})

        total = len(targets)
        logger.info(f"Target packages to inspect: {total}", f"จำนวนแอพที่ต้องตรวจสอบ: {total}")

        with self._lock:
            self.state["total_count"] = total

        detected_list = []
        summary = {
            "total_scanned": 0,
            "threats_found": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "skipped_count": 0,
            "clean_count": 0,
            "scan_type": scan_type
        }

        for idx, item in enumerate(targets):
            if self._cancel_requested:
                logger.warning("Scan aborted by user", "การสแกนถูกยกเลิกโดยผู้ใช้")
                break

            pkg = item["pkg"]
            is_sys = item["is_system"]
            is_dis = item["is_disabled"]
            installer = installer_map.get(pkg, "Unknown")
            has_acc_abuse = pkg in accessibility_abusers

            percent = int(((idx + 1) / max(1, total)) * 100)

            # Analyze package
            threat = self._evaluate_package(pkg, is_sys, is_dis, installer, has_acc_abuse, scan_type)

            if threat:
                detected_list.append(threat)
                if threat["risk"] == "CRITICAL":
                    summary["critical_count"] += 1
                elif threat["risk"] == "HIGH":
                    summary["high_count"] += 1
                elif threat["risk"] == "MEDIUM":
                    summary["medium_count"] += 1
                summary["threats_found"] += 1
                
                logger.danger(f"Found Threat: {pkg} [{threat['risk']}] ({threat['type']})", f"ตรวจพบไวรัส/มัลแวร์: {pkg}")
            else:
                if db_manager.is_whitelisted(pkg):
                    summary["skipped_count"] += 1
                else:
                    summary["clean_count"] += 1

            summary["total_scanned"] = idx + 1

            with self._lock:
                self.state["percent"] = percent
                self.state["current_package"] = pkg
                self.state["scanned_count"] = idx + 1
                self.state["threats_count"] = len(detected_list)
                self.state["threats"] = list(detected_list)
                self.state["summary"] = dict(summary)

            # Smooth pacing
            if total < 50:
                time.sleep(0.04)
            elif total < 200:
                time.sleep(0.015)
            else:
                time.sleep(0.005)

        with self._lock:
            self.scan_results = detected_list
            self.is_scanning = False
            self.state["status"] = "completed" if not self._cancel_requested else "cancelled"
            self.state["percent"] = 100
            self.state["current_package"] = f"สแกนเสร็จสิ้น (พบมัลแวร์ {len(detected_list)} รายการ)"

        logger.info(f"Scan finished! Scanned {summary['total_scanned']} apps, Found {len(detected_list)} threats.", 
                    f"สแกนเสร็จสิ้น! ตรวจสอบ {summary['total_scanned']} แอพ, พบไวรัส {len(detected_list)} รายการ")

    def _get_packages(self, dev_serial, flag):
        out, _, code = adb_manager.run_cmd(["-s", dev_serial, "shell", "pm", "list", "packages", flag])
        packages = []
        if code == 0:
            for line in out.splitlines():
                if line.startswith("package:"):
                    pkg = line.replace("package:", "").strip()
                    if pkg:
                        packages.append(pkg)
        return packages

    def _get_installer_map(self, dev_serial):
        out, _, code = adb_manager.run_cmd(["-s", dev_serial, "shell", "pm", "list", "packages", "-i"])
        imap = {}
        if code == 0:
            for line in out.splitlines():
                m = re.search(r"package:([^\s]+)\s+installer=([^\s]+)", line)
                if m:
                    imap[m.group(1)] = m.group(2)
        return imap

    def _get_accessibility_services(self, dev_serial):
        out, _, code = adb_manager.run_cmd(["-s", dev_serial, "shell", "dumpsys", "accessibility"])
        abusers = set()
        if code == 0:
            for line in out.splitlines():
                if "ServiceInfo" in line or "enabled=" in line or "/" in line:
                    for m in re.finditer(r"([a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9_\-]+)+)/", line):
                        pkg = m.group(1)
                        if not db_manager.is_whitelisted(pkg):
                            abusers.add(pkg)
        return abusers

    def _evaluate_package(self, pkg, is_system, is_disabled, installer, has_acc_abuse, scan_type):
        if scan_type == "wipe_non_essential":
            # 1. System apps are always preserved
            if is_system:
                return None

            # 2. Banking, Social Media, and Communication apps are strictly preserved
            is_protected, app_name, cat = db_manager.is_banking_or_social(pkg)
            if is_protected:
                return None

            # 3. Known malware in database marked as CRITICAL
            sig = db_manager.is_malware(pkg)
            if sig:
                return {
                    "package_name": pkg,
                    "app_name": sig.get("name", pkg),
                    "risk": "CRITICAL",
                    "type": sig.get("type", "Known Malware / Trojan"),
                    "reason": "มัลแวร์ในฐานข้อมูล (จะถูกลบทันที)",
                    "installer": installer,
                    "is_system": is_system,
                    "is_disabled": is_disabled,
                    "selected": True
                }

            # 4. Non-essential user app identified for cleaning
            return {
                "package_name": pkg,
                "app_name": f"แอพทั่วไป: {pkg}",
                "risk": "HIGH",
                "type": "General User App (ไม่ใช่โซเชียล/ธนาคาร)",
                "reason": "แอพทั่วไปที่ติดตั้งเพิ่มเติม (ล้างเพื่อความสะอาด)",
                "installer": installer,
                "is_system": is_system,
                "is_disabled": is_disabled,
                "selected": True
            }

        if db_manager.is_whitelisted(pkg):
            return None

        sig = db_manager.is_malware(pkg)
        if sig:
            return {
                "package_name": pkg,
                "app_name": sig.get("name", pkg),
                "risk": sig.get("risk", "HIGH"),
                "type": sig.get("type", "Known Malware / Banking Trojan"),
                "reason": "Virus Database Match (พบในฐานข้อมูลไวรัส)",
                "installer": installer,
                "is_system": is_system,
                "is_disabled": is_disabled,
                "selected": True
            }

        if scan_type in ["full", "smart"]:
            if has_acc_abuse and not is_system:
                return {
                    "package_name": pkg,
                    "app_name": f"Suspicious Accessibility Hijacker ({pkg})",
                    "risk": "CRITICAL",
                    "type": "Accessibility Trojan / Remote Control",
                    "reason": "Abusing Accessibility Services (แอบใช้สิทธิ์ควบคุมหน้าจอ)",
                    "installer": installer,
                    "is_system": is_system,
                    "is_disabled": is_disabled,
                    "selected": True
                }

            rules = db_manager.heuristic_rules.get("suspicious_package_patterns", [])
            for pat in rules:
                if re.search(pat, pkg, re.IGNORECASE):
                    return {
                        "package_name": pkg,
                        "app_name": f"Heuristic Threat: {pkg}",
                        "risk": "HIGH",
                        "type": "Smart Check Heuristic Detection",
                        "reason": f"Matches Malware Pattern: {pat}",
                        "installer": installer,
                        "is_system": is_system,
                        "is_disabled": is_disabled,
                        "selected": True
                    }

            if installer in ["null", "com.android.chrome", "com.sec.android.app.sbrowser", "Unknown"] and not is_system:
                if any(x in pkg for x in ["loan", "police", "revenue", "fast", "tax", "customs", "cleaner", "update", "patch", "remote"]):
                    return {
                        "package_name": pkg,
                        "app_name": f"Sideloaded Fake App: {pkg}",
                        "risk": "CRITICAL",
                        "type": "Sideloaded Banking / Phishing APK",
                        "reason": f"Installed from non-Play Store source ({installer})",
                        "installer": installer,
                        "is_system": is_system,
                        "is_disabled": is_disabled,
                        "selected": True
                    }

        return None

# Global scanner singleton
app_scanner = AppScanner()
