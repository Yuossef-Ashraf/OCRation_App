import os
import json
import logging
import time
from typing import List, Dict, Optional, Any

# Load .env and .env2 (optional)
try:
    from dotenv import load_dotenv  # type: ignore
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for fn in (".env", ".env2"):
        p = os.path.join(base_dir, fn)
        if os.path.isfile(p):
            load_dotenv(dotenv_path=p, override=False)
except ImportError:
    logging.warning("⚠️ 'python-dotenv' not installed. Environment variables might not load.")
except Exception as e:
    logging.warning(f"⚠️ Failed to load .env file: {e}")

# =========================
# Logging Configuration
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =========================
# Optional Translator
# =========================
try:
    from deep_translator import GoogleTranslator
    DEEP_TRANSLATOR_AVAILABLE = True
except Exception:
    GoogleTranslator = None
    DEEP_TRANSLATOR_AVAILABLE = False


# ============================================================
# PART A: Provider-Agnostic LLM Adapter
# ============================================================

class LLMProvider:
    """
    Abstract base (duck-typed) for LLM Providers.
    """
    def is_available(self) -> bool:
        raise NotImplementedError

    def call(self, system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 512) -> str:
        raise NotImplementedError

class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.msg_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self._initialized = bool(self.api_key)
        
        if self._initialized:
             logger.info(f"✅ Groq Provider initialized | Model: {self.model}")
        else:
             logger.warning("⚠️ GROQ_API_KEY environment variable missing")

    def is_available(self) -> bool:
        return self._initialized

    def call(self, system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 512) -> str:
        if not self.is_available():
            raise RuntimeError("GROQ_API_KEY is not set")
            
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens, # Note: Groq API uses max_tokens, standard OpenAI uses max_completion_tokens sometimes
            "top_p": 1,
            "stream": False
        }

        # Retry logic: 1 retry for transient failures
        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(self.msg_url, json=payload, headers=headers, timeout=30)
                
                if response.status_code != 200:
                    # Log the full error to help debug
                    logger.error(f"Groq API Error ({response.status_code}): {response.text}")
                    raise Exception(f"API Error {response.status_code}: {response.text}")
                    
                data = response.json()
                return data["choices"][0]["message"]["content"] or ""
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM call failed (Attempt {attempt+1}): {e}. Retrying...")
                    time.sleep(1) # Short backoff
                else:
                    logger.error(f"LLM call failed permanently: {e}")
                    raise e
        return ""

# Initialize global provider
# In future, we can swap this with AntigravityProvider()
_current_provider = GroqProvider()


# ============================================================
# PART B: Entity Extraction (JSON-Only)
# ============================================================

def _parse_json_safely(raw_text: str) -> Dict[str, str]:
    """
    Attempts to extract and parse JSON from raw LLM output.
    """
    try:
        # 1. Find the substring between { and }
        start = raw_text.find('{')
        end = raw_text.rfind('}')
        
        if start == -1 or end == -1:
            return {}

        json_str = raw_text[start:end+1]
        
        # 2. Parse
        data = json.loads(json_str)
        
        if not isinstance(data, dict):
            return {}
            
        return data
    except Exception:
        return {} # Parse failed

def extract_entities_json(text: str) -> Dict[str, str]:
    """
    Extracts specific entities (email, phone, name, address) as JSON.
    """
    if not text or not _current_provider.is_available():
        return {}

    system_prompt = (
        "You are a strict JSON extraction engine.\n"
        "Your task is to extract specific entities from the input text.\n"
        "Output MUST be valid JSON only. No markdown, no explanations.\n"
        "Rules:\n"
        "1. Required keys: \"email\", \"phone\", \"name\", \"address\".\n"
        "2. If a value is not found, set it to generic empty string \"\".\n"
        "3. Extract exact values from text (do not fix spelling or punctuation).\n"
        "4. Choose the most complete candidate if multiple exist.\n"
    )
    
    try:
        raw_output = _current_provider.call(
            system_prompt=system_prompt,
            user_prompt=text,
            temperature=0.0, # Deterministic
            max_tokens=256
        )
        
        data = _parse_json_safely(raw_output)
        
        # Validate keys and ensure strings
        safe_data = {
            "email": str(data.get("email") or ""),
            "phone": str(data.get("phone") or ""),
            "name": str(data.get("name") or ""),
            "address": str(data.get("address") or "")
        }
        
        # Check if we actually found anything (at least one non-empty value)
        if any(v.strip() for v in safe_data.values()):
            return safe_data
            
        return {} # Treat as failure if all empty
        
    except Exception as e:
        logger.error(f"JSON Extraction failed: {e}")
        return {}


# ============================================================
# PART C: Entities-Only Formatting output
# ============================================================

def format_entities_text(entities: Dict[str, str], order_list: List[str]) -> str:
    """
    Constructs the final text string manually from extracted entities.
    """
    lines = []
    
    # Normalize order list keys to lowercase for matching
    # Map display names to keys if needed, but assuming simple mapping for now
    key_map = {
        "email": "email",
        "phone": "phone",
        "name": "name",
        "address": "address"
    }
    
    seen_keys = set()
    
    for item in order_list:
        key = item.lower().strip()
        mapped_key = key_map.get(key, key) # Fallback to item itself
        
        if mapped_key in entities:
             val = entities[mapped_key]
             if val.strip():
                 # Capitalize Label for display: "email" -> "Email"
                 label = item.strip().capitalize()
                 lines.append(f"{label}: {val}")
        
        seen_keys.add(mapped_key)
        
    # Append any standard keys that were populated but NOT in the requested order (Optional logic? 
    # Spec says "output lines for each key in entity_order". It doesn't say "append others". 
    # Current behavior implies strict adherence to requested order.)
    
    return "\n".join(lines)


# ============================================================
# PART D: Fallback Formatting / Reordering
# ============================================================

def fallback_reformat_text(text: str, order_list: List[str]) -> str:
    """
    Uses LLM to reformat text if JSON extraction fails.
    Includes safety guards against hallucinations.
    """
    if not text or not _current_provider.is_available():
        return text

    order_str = ", ".join(order_list)
    system_prompt = (
        "You are a text formatter.\n"
        f"Goal: Reformat the input text to prioritize these fields: {order_str}.\n"
        "Rules:\n"
        "- Do NOT invent data.\n"
        "- Do NOT change correct digits or letters.\n"
        "- Bring the requested fields to the top if found.\n"
        "- Keep the rest of the text as is or minimally cleaned.\n"
    )
    
    try:
        new_text = _current_provider.call(
            system_prompt=system_prompt,
            user_prompt=text,
            temperature=0.1,
            max_tokens=len(text) + 200 # Allow some room but limit excessive generation
        )
        
        # Safety Guard
        if not new_text:
            return text
            
        # Reject if output is suspiciously longer (hallucination check)
        # Allow 50% growth for formatting overhead, but doubling is suspicious
        if len(new_text) > len(text) * 1.5 + 50:
            logger.warning("Fallback reformat rejected: Output too long (Hallucination risk)")
            return text
            
        return new_text
        
    except Exception as e:
        logger.error(f"Fallback reformat failed: {e}")
        return text


# ============================================================
# PART E: Main Pipeline Integration
# ============================================================

def is_llm_available() -> bool:
    return _current_provider.is_available()

def organize_entities(text: str, order_list: Optional[List[str]]) -> str:
    """
    Orchestrates the LLM post-processing pipeline.
    """
    if not text or not is_llm_available() or not order_list:
        return text

    # Filter empty items
    valid_order = [item.strip() for item in order_list if item and item.strip()]
    if not valid_order:
        return text

    logger.info(f"Processing Text Order: {valid_order}")

    # 1. Attempt JSON Extraction (Primary Path)
    entities = extract_entities_json(text)
    
    if entities:
        logger.info("✅ Entity Extraction successful. Formatting manually.")
        formatted = format_entities_text(entities, valid_order)
        # If the format resulted in empty string (e.g. entities found but none matched requested order), 
        # fall back? Or return empty? 
        # Spec says "if valid entities exist -> replace final_text". 
        # If it returns empty string, that might be bad UX. 
        # Let's say if formatted has content, return it. Else fallback.
        if formatted.strip():
            return formatted
            
    # 2. Fallback Path (Secondary Path)
    logger.info("⚠️ JSON Extraction empty/partial. Using Fallback Reformat.")
    return fallback_reformat_text(text, valid_order)


# ============================================================
# Utilities (Translation / Summarization) - Kept for compatibility
# ============================================================

def summarize_text(text: str) -> str:
    if not is_llm_available():
        return text
    try:
        return _current_provider.call(
            system_prompt="Summarize the following text concisely.",
            user_prompt=text,
            max_tokens=256
        )
    except Exception:
        return text

def translate_text(text: str, target_lang: str) -> str:
    # 1. Try Deep Translator (Google) first - Fast & Free
    if DEEP_TRANSLATOR_AVAILABLE and GoogleTranslator:
        try:
            return GoogleTranslator(source='auto', target=target_lang).translate(text)
        except Exception as e:
            logger.warning(f"DeepTranslator failed: {e}")
    
    # 2. Fallback to LLM
    if is_llm_available():
        try:
            lang_name = "Arabic" if target_lang == "ar" else "English"
            return _current_provider.call(
                system_prompt=f"Translate this text to {lang_name}. Output only the translation.",
                user_prompt=text
            )
        except Exception:
            return text
            
    return text


def translate(text: str, target_lang: str = "ar") -> str:
    """
    Translate text to the target language.
    
    Args:
        text: Input text string
        target_lang: Language code (default 'ar')
        
    Returns:
        str: Translated text or empty string if input is empty
    """
    if not text or not str(text).strip():
        return ""
    return translate_text(str(text), target_lang=target_lang)

