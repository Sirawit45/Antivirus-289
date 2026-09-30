import threading
import time
from .adb_manager import adb_manager
from .logger import logger

class AppCleaner:
    def __init__(self):
        self.is_cleaning = False
        self._cancel_requested = False
        self._lock = threading.Lock()
        self.state = {
            "status": "idle",  # "idle", "cleaning", "completed", "cancelled"
            "percent": 0,
            "current_package": "",
            "index": 0,
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "cleaned_packages": []
        }

    def get_state(self):
        with self._lock:
            return dict(self.state)

    def cancel_cleaning(self):
        with self._lock:
            self._cancel_requested = True
            self.state["status"] = "cancelled"
        logger.warning("Operation cancelled by user", "ผู้ใช้ยกเลิกการทำงานลบทั้งหมด")

    def uninstall_package(self, package_name, is_system=False):
        """Uninstall a single package (synchronous call for single item)"""
        dev_serial = adb_manager.connected_device or ("SIMULATOR-289-VIP" if adb_manager.simulator_mode else None)
        if not dev_serial:
            return False, "No device connected"

        logger.danger(f"User App - ลบ: {package_name}...", "กำลังดำเนินการลบ")

        # 1. Standard adb uninstall
        out, err, code = adb_manager.run_cmd(["-s", dev_serial, "uninstall", package_name])
        if "Success" in out or "Success" in err:
            logger.success(f"User App - ลบ: {package_name}... Success", "ลบสำเร็จ")
            return True, "Success"

        # 2. Fallback: pm uninstall for user 0
        out2, err2, code2 = adb_manager.run_cmd(["-s", dev_serial, "shell", "pm", "uninstall", "-k", "--user", "0", package_name])
        if "Success" in out2 or "Success" in err2:
            logger.success(f"User App (User 0) - ลบ: {package_name}... Success", "ลบสำเร็จ")
            return True, "Success"

        # 3. Fallback: disable system app
        if is_system:
            out3, err3, code3 = adb_manager.run_cmd(["-s", dev_serial, "shell", "pm", "disable-user", "--user", "0", package_name])
            if "disabled" in out3.lower() or code3 == 0:
                logger.success(f"System App - ปิดการทำงาน: {package_name}... Success", "ปิดการทำงานสำเร็จ")
                return True, "Disabled System App"

        logger.warning(f"Failed to remove {package_name}: {out or err or out2 or err2}", "ไม่สามารถลบได้")
        return False, err or out or "Failed"

    def start_clean_async(self, threat_list):
        """Start cleaning batch in background thread"""
        with self._lock:
            if self.is_cleaning:
                return False
            self.is_cleaning = True
            self._cancel_requested = False
            self.state = {
                "status": "cleaning",
                "percent": 0,
                "current_package": "กำลังเตรียมการลบ...",
                "index": 0,
                "total": len(threat_list),
                "success_count": 0,
                "fail_count": 0,
                "cleaned_packages": []
            }

        t = threading.Thread(target=self._clean_worker, args=(threat_list,), daemon=True)
        t.start()
        return True

    def _clean_worker(self, threat_list):
        total = len(threat_list)
        logger.info(f"Starting removal of {total} threats...", f"เริ่มลบมัลแวร์ {total} รายการ...")

        success_count = 0
        fail_count = 0
        cleaned_packages = []

        for idx, item in enumerate(threat_list):
            if self._cancel_requested:
                logger.warning("Cleaning aborted by user", "ผู้ใช้ยกเลิกการทำงานลบทั้งหมด")
                break

            pkg = item.get("package_name") or item.get("pkg")
            is_sys = item.get("is_system", False)

            percent = int(((idx + 1) / max(1, total)) * 100)

            ok, msg = self.uninstall_package(pkg, is_system=is_sys)
            if ok:
                success_count += 1
                cleaned_packages.append(pkg)
            else:
                fail_count += 1

            with self._lock:
                self.state["percent"] = percent
                self.state["current_package"] = pkg
                self.state["index"] = idx + 1
                self.state["success_count"] = success_count
                self.state["fail_count"] = fail_count
                self.state["cleaned_packages"] = list(cleaned_packages)

            time.sleep(0.08)

        with self._lock:
            self.is_cleaning = False
            self.state["status"] = "completed" if not self._cancel_requested else "cancelled"
            self.state["percent"] = 100
            self.state["current_package"] = "การลบเสร็จสิ้น"

        logger.success(f"{success_count} User Apps Removed ({fail_count} failed)", f"ลบแอพเสร็จสิ้น {success_count} แอพ")
        adb_manager.refresh_device_info()

# Global cleaner singleton
app_cleaner = AppCleaner()
