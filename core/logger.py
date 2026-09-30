import os
import sys
import datetime
import threading
from . import get_app_dir

class AppLogger:
    def __init__(self, log_file_path=None):
        if log_file_path is None:
            base_dir = get_app_dir()
            self.log_file_path = os.path.join(base_dir, "logs.txt")
        else:
            self.log_file_path = log_file_path

        self.listeners = []
        self._lock = threading.Lock()
        self.logs_history = []

    def subscribe(self, callback):
        with self._lock:
            if callback not in self.listeners:
                self.listeners.append(callback)

    def unsubscribe(self, callback):
        with self._lock:
            if callback in self.listeners:
                self.listeners.remove(callback)

    def log(self, message, level="INFO", thai_message=""):
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

        full_display = message
        if thai_message:
            full_display = f"{message} - {thai_message}"

        log_entry = {
            "timestamp": timestamp_str,
            "level": level,
            "message": message,
            "thai_message": thai_message,
            "full_text": full_display
        }

        with self._lock:
            self.logs_history.append(log_entry)
            if len(self.logs_history) > 500:
                self.logs_history.pop(0)

            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{timestamp_str} : - {full_display}\n")
            except Exception:
                pass

            for listener in list(self.listeners):
                try:
                    listener(log_entry)
                except Exception:
                    pass

    def info(self, msg, thai=""):
        self.log(msg, level="INFO", thai_message=thai)

    def success(self, msg, thai=""):
        self.log(f"✅ {msg}", level="SUCCESS", thai_message=thai)

    def warning(self, msg, thai=""):
        self.log(f"⚠️ {msg}", level="WARNING", thai_message=thai)

    def danger(self, msg, thai=""):
        self.log(f"⚔️ {msg}", level="DANGER", thai_message=thai)

    def smart(self, msg, thai=""):
        self.log(f"🧠 {msg}", level="SMART", thai_message=thai)

    def get_history(self):
        with self._lock:
            return list(self.logs_history)

    def clear(self):
        with self._lock:
            self.logs_history.clear()

# Global logger singleton
logger = AppLogger()
