import time
import logging
import bcrypt
import re
from typing import Dict, List, Optional
from flask import request, jsonify
from functools import wraps

# Setup specialized security logger
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)
handler = logging.FileHandler("logs/security.log")
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [IP:%(clientip)s] %(message)s'))
security_logger.addHandler(handler)

class SecurityManager:
    def __init__(self):
        self.admin_hash: Optional[bytes] = None
        self.otp_tokens = set()
        
        # Abuse Control
        self.requests: Dict[str, List[float]] = {}
        self.violations: Dict[str, int] = {}
        self.blacklist: Dict[str, float] = {} # IP -> Expiry Timestamp
        
    def log(self, event_type: str, message: str, ip: str = None):
        if not ip:
            ip = "UNKNOWN"
        extra = {'clientip': ip}
        security_logger.info(f"[{event_type}] {message}", extra=extra)

    # --- Secret Protection ---
    def set_admin_key(self, plain_key: str):
        """Hashes and stores the admin key. Never stores plain text."""
        salt = bcrypt.gensalt()
        self.admin_hash = bcrypt.hashpw(plain_key.encode('utf-8'), salt)
        # Clear plain key from memory explicitly if possible (Python GC makes this hard, but we don't hold ref)

    def verify_token(self, input_token: str) -> Optional[str]:
        """Returns auth type ('ADMIN', 'OTP') or None."""
        if not input_token:
            return None
            
        # Check Admin
        if self.admin_hash:
            try:
                if bcrypt.checkpw(input_token.encode('utf-8'), self.admin_hash):
                    return "ADMIN"
            except Exception:
                pass
        
        # Check OTP
        if input_token in self.otp_tokens:
            self.otp_tokens.remove(input_token)
            return "OTP"
            
        return None

    def generate_otp(self) -> str:
        import random
        code = str(random.randint(100000, 999999))
        self.otp_tokens.add(code)
        return code

    # --- Abuse Control ---
    def is_blacklisted(self, ip: str) -> bool:
        if ip in self.blacklist:
            if time.time() < self.blacklist[ip]:
                self.log("BLACKLIST_BLOCK", "Blocked request from blacklisted IP", ip)
                return True
            else:
                del self.blacklist[ip] # Expired
        return False

    def record_violation(self, ip: str):
        self.violations[ip] = self.violations.get(ip, 0) + 1
        self.log("VIOLATION", f"Violation count: {self.violations[ip]}", ip)
        
        if self.violations[ip] >= 5: # Ban after 5 violations
            expiry = time.time() + 900 # 15 minutes
            self.blacklist[ip] = expiry
            self.log("BLACKLIST_ADD", "IP Banned for 15 minutes", ip)

    def check_rate_limit(self, ip: str, limit: int, window: int) -> bool:
        if self.is_blacklisted(ip):
            return False
            
        now = time.time()
        if ip not in self.requests:
            self.requests[ip] = []
            
        # Filter old
        self.requests[ip] = [t for t in self.requests[ip] if now - t < window]
        
        if len(self.requests[ip]) >= limit:
            self.record_violation(ip)
            return False
            
        self.requests[ip].append(now)
        return True

    # --- AI Safety ---
    def sanitize_ai_output(self, text: str) -> str:
        """Removes dangerous HTML/JS from AI output."""
        if not text: return ""
        
        # Block script tags
        clean = re.sub(r'<script.*?>.*?</script>', '[BLOCKED_SCRIPT]', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Block event handlers
        clean = re.sub(r' on\w+=".*?"', '', clean, flags=re.IGNORECASE)
        
        # Block javascript: URIs
        clean = re.sub(r'javascript:', 'blocked:', clean, flags=re.IGNORECASE)
        
        if clean != text:
            self.log("AI_SANITIZATION", "Malicious content removed from AI output")
            
        return clean

# Singleton Instance
security = SecurityManager()

# Decorator
def require_rate_limit(limit=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.remote_addr or "127.0.0.1"
            if not security.check_rate_limit(ip, limit, window):
                security.log("RATE_LIMIT", f"Exceeded {limit}/{window}s", ip)
                return jsonify({"error": "Too many requests. You are temporarily blocked."}), 429
            if security.is_blacklisted(ip):
                 return jsonify({"error": "Access Denied (Blacklisted)"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
