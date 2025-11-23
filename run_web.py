"""
OCRATION - Web Application Server
Loads env from:
  - .env  (GROQ_API_KEY)
  - .env2 (OCR_SPACE_API_KEY)  -> ALWAYS overrides old env values
Robust loader for Windows (UTF-16/UTF-8-SIG supported)
"""

import os
import sys
import logging
import importlib.util
from typing import Dict, List, Tuple, Optional

werkzeug_log = logging.getLogger("werkzeug")
werkzeug_log.setLevel(logging.WARNING)


def _print_block(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _module_exists(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def check_dependencies() -> Tuple[bool, List[str], List[str]]:
    required: Dict[str, str] = {
        "flask": "Flask",
        "requests": "requests",
        "numpy": "numpy",
        "cv2": "opencv-python",
    }
    optional: Dict[str, str] = {
        "groq": "groq",
        "deep_translator": "deep-translator",
        "OpenSSL": "pyopenssl",
        "cryptography": "cryptography",
        "dotenv": "python-dotenv",
    }

    missing_required = [pkg for mod, pkg in required.items() if not _module_exists(mod)]
    missing_optional = [pkg for mod, pkg in optional.items() if not _module_exists(mod)]
    return (len(missing_required) == 0), missing_required, missing_optional


def _read_text_any_encoding(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()

    for enc in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252"):
        try:
            return data.decode(enc)
        except Exception:
            continue

    return data.decode("utf-8", errors="ignore")


def _strip_quotes(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and ((v[0] == v[-1]) and v[0] in ("'", '"')):
        return v[1:-1]
    return v


def _parse_env_line(line: str) -> Optional[Tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if line.lower().startswith("export "):
        line = line[7:].strip()

    sep = "=" if "=" in line else (":" if ":" in line else None)
    if not sep:
        return None

    key, val = line.split(sep, 1)
    key = key.strip()
    val = _strip_quotes(val.strip())

    if not key:
        return None
    return key, val


def load_env_file(path: str, override: bool) -> Dict[str, str]:
    loaded: Dict[str, str] = {}
    if not os.path.isfile(path):
        return loaded

    content = _read_text_any_encoding(path)
    for raw_line in content.splitlines():
        parsed = _parse_env_line(raw_line)
        if not parsed:
            continue
        k, v = parsed
        if not override and os.environ.get(k):
            continue
        os.environ[k] = v
        loaded[k] = v
    return loaded


def load_env_pair(root_dir: str, web_dir: str) -> Dict[str, str]:
    """
    Loads .env file from root and web directories.
    """
    loaded_all: Dict[str, str] = {}

    for d in (root_dir, web_dir):
        p = os.path.join(d, ".env")
        loaded_all.update(load_env_file(p, override=True))

    return loaded_all


def _find_app_dir(base_dir: str) -> str:
    candidates = [base_dir, os.path.join(base_dir, "web")]
    for d in candidates:
        if os.path.isfile(os.path.join(d, "app.py")):
            return d
    raise FileNotFoundError("Could not find app.py in project root or ./web")


def _import_flask_app(app_dir: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    spec = importlib.util.spec_from_file_location("app", os.path.join(app_dir, "app.py"))
    if spec is None or spec.loader is None:
        raise ImportError("Failed to load app.py spec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore

    if not hasattr(module, "app"):
        raise AttributeError("app.py does not expose variable named 'app'")

    return module.app


def _env_status_print():
    ocr_key = (os.environ.get("OCR_SPACE_API_KEY") or "").strip()
    if ocr_key:
        print(f"[OK] OCR_SPACE_API_KEY loaded ✅ ({ocr_key[:4]}...{ocr_key[-4:]})")
    else:
        print("[WARNING] OCR_SPACE_API_KEY is NOT set. (Expected in .env)")

    groq_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if groq_key:
        print("[OK] GROQ_API_KEY loaded ✅")
    else:
        print("[INFO] GROQ_API_KEY not set. LLM features disabled (OK).")


try:
    _print_block("OCRATION - Initializing Web Server")

    print("[1/5] Checking dependencies...")
    ok, missing_required, missing_optional = check_dependencies()
    if not ok:
        _print_block("ERROR: Missing REQUIRED packages")
        for pkg in missing_required:
            print(f"  [MISSING] {pkg}")
        print("\nInstall them with:")
        print(f"  pip install {' '.join(missing_required)}")
        sys.exit(1)

    print("[OK] Required dependencies found")
    if missing_optional:
        print("[INFO] Optional packages missing (features will be limited):")
        for pkg in missing_optional:
            print(f"  - {pkg}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = _find_app_dir(base_dir)

    print("[2/5] Loading .env + .env2 (robust)...")
    loaded = load_env_pair(root_dir=base_dir, web_dir=app_dir)
    print(f"[OK] Loaded keys: {', '.join(sorted(loaded.keys())) if loaded else '(none)'}")

    print("[3/5] Checking env status...")
    _env_status_print()

    print("[4/5] Loading Flask application...")
    print(f"[OK] Found app.py in: {app_dir}")
    flask_app = _import_flask_app(app_dir)
    print("[OK] Flask app loaded successfully")

    import socket
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    if __name__ == "__main__":
        local_ip = get_local_ip()
        
        # 1. Setup Admin Token
        # Use a fixed key for the verified user or ask via env/input in future
        # For now, we will use a strong default or generate one.
        # User requested: "My personal mobile only". We can set a specific key.
        admin_key = "MY-SECRET-MASTER-KEY"  # You can change this to whatever you want
        flask_app.security.set_admin_key(admin_key)
        
        # 2. Generate One-Time Tokens
        otps = [flask_app.security.generate_otp() for _ in range(5)]
        
        _print_block("OCRATION - Secured Server Started")
        print(f"  💻 Local Admin URL:   http://127.0.0.1:5000  (Open this on Laptop)")
        print(f"  📱 Mobile Access URL: http://{local_ip}:5000  (Open this on Mobile)")
        print("\n  🔐 ACCESS CODES:")
        print(f"     [Admin Master Key]: {admin_key}  (Use this on YOUR mobile - Permanent)")
        print(f"     [One-Time Tickets]: {', '.join(otps)}  (Give these to guests - Valid once)")
        print("  Press CTRL+C to stop server\n")

        flask_app.run(
            debug=False,
            host="0.0.0.0", # Listening on all interfaces for Mobile access
            port=5000,
            use_reloader=False,
            threaded=True
        )

except KeyboardInterrupt:
    _print_block("Server stopped by user (CTRL+C)")
    sys.exit(0)

except Exception as e:
    _print_block("ERROR: Failed to start server")
    print(f"  {type(e).__name__}: {e}")
    print("=" * 70)
    import traceback
    traceback.print_exc()
    sys.exit(1)
