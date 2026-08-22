"""Translation service — detect and translate patient-facing text.

Uses the fast Groq model (get_llm(fast=True)) for language detection and
translation. Translation does not need tool-calling or reasoning capabilities.

Agents always reason and call tools in English internally. Only the outer
request/response layer is language-aware:
  - Incoming non-English requests are translated to English before the graph.
  - Outgoing patient-facing text (confirmations, billing, reminders) is
    translated back into the patient's preferred_language after the graph.
"""

from app.core.llm.groq_client import get_llm

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "hi": "Hindi",
    "ur": "Urdu",
}


def detect_language(text: str) -> str:
    """Detect the language of *text*. Returns an ISO 639-1 code (e.g. 'es', 'ar').

    Falls back to ``'en'`` when the model cannot determine the language, when
    the text is already English, or when the LLM is unavailable.
    """
    try:
        llm = get_llm(fast=True)
    except RuntimeError:
        return "en"
    prompt = (
        "You are a language detection utility. Reply with ONLY the two-letter "
        "ISO 639-1 language code for the following text. Do not add any other "
        "text, explanation, or punctuation. If the text is empty or you are "
        "uncertain, reply with 'en'.\n\n"
        f"Text: {text}"
    )
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        code = response.content.strip().lower()[:2]
        if code in SUPPORTED_LANGUAGES:
            return code
    except Exception:  # noqa: BLE001
        pass
    return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """Translate *text* from *source_lang* into English.

    If *source_lang* is ``'en'`` or translation fails, returns *text* unchanged.
    """
    if source_lang == "en" or not text.strip():
        return text
    try:
        llm = get_llm(fast=True)
    except RuntimeError:
        return text
    lang_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
    prompt = (
        f"Translate the following {lang_name} text into English. "
        "Return ONLY the translated text, no explanation or formatting.\n\n"
        f"{text}"
    )
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        translated = response.content.strip()
        return translated if translated else text
    except Exception:  # noqa: BLE001
        return text


def translate_from_english(text: str, target_lang: str) -> str:
    """Translate English *text* into *target_lang*.

    If *target_lang* is ``'en'`` or translation fails, returns *text* unchanged.
    """
    if target_lang == "en" or not text.strip():
        return text
    try:
        llm = get_llm(fast=True)
    except RuntimeError:
        return text
    lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    prompt = (
        f"Translate the following English text into {lang_name}. "
        "Return ONLY the translated text, no explanation or formatting.\n\n"
        f"{text}"
    )
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        translated = response.content.strip()
        return translated if translated else text
    except Exception:  # noqa: BLE001
        return text
