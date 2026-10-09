"""
SENA — Smart Enterprise & Network Archive
Launcher Otomatis (1-Click Run)

Skrip ini memudahkan siapa pun untuk menjalankan SENA tanpa setup rumit.
Cukup jalankan:
    python run.py
"""

import sys
import os
import time
import webbrowser
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI colors for friendly terminal
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}==================================================================
   S E N A  --  AI Knowledge Search Hub (Local & 100% Offline)
=================================================================={RESET}
  * Hybrid Retrieval: BM25 (Kata Kunci) + Vektor (Makna Semantik)
  * AI Generatif: Qwen 2.5 1.5B Instruct GGUF (Lokal di Laptop)
  * Biaya Cloud: $0 (Gratis Selamanya, Tanpa OpenAI / Cloud API)
------------------------------------------------------------------
"""
    print(banner)


def check_python_version():
    if sys.version_info < (3, 10):
        print(f"{RED}[ERROR] Python versi 3.10 atau lebih baru dibutuhkan.{RESET}")
        print(f"Versi terdeteksi: {sys.version}")
        sys.exit(1)


def check_dependencies():
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("jinja2", "jinja2"),
        ("pydantic", "pydantic"),
        ("watchdog", "watchdog"),
        ("sentence_transformers", "sentence-transformers"),
        ("fitz", "pymupdf"),
        ("docx", "python-docx")
    ]
    missing = []
    for mod_name, pkg_name in required_packages:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg_name)

    if missing:
        print(f"{YELLOW}[PERINGATAN] Beberapa paket belum terpasang: {', '.join(missing)}{RESET}")
        print(f"Jalankan perintah ini terlebih dahulu:\n  {BOLD}pip install -r requirements.txt{RESET}\n")
        choice = input("Apakah Anda ingin memasangnya sekarang secara otomatis? (y/n): ").strip().lower()
        if choice in ("y", "yes"):
            print(f"{CYAN}Memasang dependensi via pip...{RESET}")
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        else:
            print(f"{RED}Dibatalkan. Silakan pasang dependensi dan jalankan ulang.{RESET}")
            sys.exit(1)


def check_directories():
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    models_dir = data_dir / "models"
    sample_dir = data_dir / "sample_docs"

    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    try:
        from app.config import settings
        target_name = settings.LLM_MODEL_NAME
    except Exception:
        target_name = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

    model_file = models_dir / target_name
    if model_file.is_file() and model_file.stat().st_size > 50 * 1024 * 1024:
        size_mb = round(model_file.stat().st_size / (1024 * 1024), 1)
        print(f"{GREEN}[OK] Model AI Terdeteksi:{RESET} {target_name} ({size_mb} MB) - Siap digunakan!")
    else:
        print(f"{YELLOW}! Model AI Belum Lengkap:{RESET} {target_name}")
        print(f"  Pencarian Hybrid tetap bekerja 100%. Model AI dapat diunduh kapan saja")
        print(f"  dengan 1-klik langsung dari Web UI (pojok kanan atas).")


def download_model_cli():
    """Download model via CLI if requested."""
    import urllib.request
    try:
        from app.config import settings
        model_name = settings.LLM_MODEL_NAME
        repo_id = settings.LLM_REPO_ID
    except Exception:
        model_name = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
        repo_id = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"

    base_dir = Path(__file__).resolve().parent
    model_path = base_dir / "data" / "models" / model_name
    url = f"https://huggingface.co/{repo_id}/resolve/main/{model_name}"

    print(f"{CYAN}Mengunduh {model_name} dari {repo_id}...{RESET}")
    print(f"URL: {url}")
    print(f"Tujuan: {model_path}")

    # Use curl if available for fast resumed download
    try:
        res = subprocess.run(["curl.exe", "-L", "-C", "-", url, "-o", str(model_path)], check=True)
        if res.returncode == 0:
            print(f"{GREEN}[OK] Berhasil mengunduh model AI!{RESET}")
            return
    except Exception:
        pass

    print(f"{YELLOW}Mengunduh via Python urllib...{RESET}")
    urllib.request.urlretrieve(url, str(model_path))
    print(f"{GREEN}[OK] Berhasil mengunduh model AI!{RESET}")


def launch_browser(url: str):
    time.sleep(1.8)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    print_banner()
    check_python_version()

    if "--download-model" in sys.argv:
        download_model_cli()
        return

    check_dependencies()
    check_directories()

    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"

    print(f"\n{GREEN}{BOLD}Memulai Server SENA...{RESET}")
    print(f"Akses Web UI di: {CYAN}{BOLD}{url}{RESET}")
    print(f"{YELLOW}(Tekan Ctrl+C di terminal ini untuk mematikan server){RESET}\n")

    # Start browser opener in background thread
    import threading
    threading.Thread(target=launch_browser, args=(url,), daemon=True).start()

    # Start Uvicorn
    import uvicorn
    uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
