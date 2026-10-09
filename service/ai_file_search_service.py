import sys
import os
import time
import logging
import threading
from pathlib import Path

# Ensure app is on path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False

import uvicorn
from app.config import settings

logger = logging.getLogger("ai_file_search.service")


class AIFileSearchService(win32serviceutil.ServiceFramework if PYWIN32_AVAILABLE else object):
    _svc_name_ = "AIFileSearchService"
    _svc_display_name_ = "AI File Search Local Service"
    _svc_description_ = "Windows Service providing local hybrid semantic and lexical document indexing and retrieval."

    def __init__(self, args):
        if PYWIN32_AVAILABLE:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server = None
        self.server_thread = None

    def SvcStop(self):
        if PYWIN32_AVAILABLE:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
        if self.server:
            self.server.should_exit = True
        logger.info("Service stop requested.")

    def SvcDoRun(self):
        if PYWIN32_AVAILABLE:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )
        logger.info("AI File Search Windows Service is starting...")

        config = uvicorn.Config(
            "app.main:app",
            host=settings.APP_HOST,
            port=settings.APP_PORT,
            log_level="info"
        )
        self.server = uvicorn.Server(config)
        self.server.run()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Development mode runner
        print(f"Starting AI File Search on http://{settings.APP_HOST}:{settings.APP_PORT}...")
        uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=False)
    else:
        if PYWIN32_AVAILABLE:
            win32serviceutil.HandleCommandLine(AIFileSearchService)
        else:
            print("pywin32 is not installed. Windows service commands unavailable.")
