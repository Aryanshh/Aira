from typing import Any, Dict

# Appendix B: Message templates (English and Hindi)
MESSAGE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "sos.alert": {
        "en": "SOS alert: {elder} needs help. Please contact them now. Time: {time}. I'm responding: {link}",
        "hi": "SOS अलर्ट: {elder} को मदद चाहिए। कृपया तुरंत संपर्क करें। समय: {time}। मैं जवाब दे रहा/रही हूँ: {link}",
    },
    "sos.failed": {
        "en": "The SOS alert for {elder} could not be delivered. Please call their contacts directly.",
        "hi": "{elder} का SOS अलर्ट भेजा नहीं जा सका। कृपया सीधे उनके संपर्कों को फ़ोन करें।",
    },
    "sos.live_banner": {
        "en": "Emergency SOS triggered for {elder_name}.",
        "hi": "{elder_name} के लिए आपातकालीन SOS सक्रिय हुआ है।",
    },
    "missed.summary": {
        "en": "{elder} missed {count} medicine(s) today: {names}.",
        "hi": "आज {elder} की {count} दवा(एँ) छूट गईं: {names}।",
    },
    "refill.low": {
        "en": "{medicine} for {elder} has about {days} day(s) of stock left. Please arrange a refill.",
        "hi": "{elder} की {medicine} का स्टॉक लगभग {days} दिन का बचा है। कृपया रीफ़िल करवाएँ।",
    },
    "refill.out": {
        "en": "{medicine} for {elder} has run out.",
        "hi": "{elder} की {medicine} खत्म हो गई है।",
    },
    "elder.reminder": {
        "en": "Time for your medicine: {medicine}.",
        "hi": "आपकी दवा का समय हो गया है: {medicine}।",
    },
    "elder.pin_locked": {
        "en": "Too many wrong PIN attempts for {elder}. Sign-in is locked for 15 minutes.",
        "hi": "{elder} के लिए गलत पिन बहुत बार डाला गया। साइन-इन 15 मिनट के लिए बंद है।",
    },
    "disclaimer": {
        "en": "Reminders follow the schedule entered by your care team. AIRA does not give medical advice.",
        "hi": "रिमाइंडर आपकी केयर टीम द्वारा दर्ज शेड्यूल के अनुसार हैं। AIRA चिकित्सीय सलाह नहीं देता।",
    },
    "sos.elder_sent": {
        "en": "Help has been requested. Stay where you are.",
        "hi": "मदद माँगी गई है। आप जहाँ हैं वहीं रहें।",
    },
    "sos.elder_offline": {
        "en": "No internet. Please call now.",
        "hi": "इंटरनेट नहीं है। कृपया अभी फ़ोन करें।",
    },
    "sos.test": {
        "en": "AIRA Care Test: Verified test alert for {elder}. Communication channels (Call & Msg) are working properly.",
        "hi": "AIRA Care टेस्ट: {elder} के लिए सत्यापित टेस्ट अलर्ट। कॉल और मैसेज प्रणाली सक्रिय है।",
    },
    "sos.call": {
        "en": "Emergency alert from AIRA Care. Your loved one {elder} has requested assistance. Please check the AIRA app or contact them immediately.",
        "hi": "AIRA Care से आपातकालीन सूचना। आपके प्रियजन {elder} ने सहायता का अनुरोध किया है। कृपया तुरंत संपर्क करें।",
    },
    "sos.checkin": {
        "en": "AIRA Care Message: Wellness update for {elder}. Please check the app for medicines & status.",
        "hi": "AIRA Care संदेश: {elder} के लिए स्वास्थ्य अपडेट। दवाओं और स्थिति के लिए ऐप देखें।",
    },
}


def render_template(template_key: str, language: str = "en", params: Dict[str, Any] = None) -> str:
    """Render a notification message template with fallback to English."""
    params = params or {}
    lang = language if language in ("en", "hi") else "en"

    template_dict = MESSAGE_TEMPLATES.get(template_key)
    if not template_dict:
        # Fallback to key and formatted params
        return f"{template_key}: {params}"

    template = template_dict.get(lang) or template_dict.get("en", "")
    try:
        return template.format(**params)
    except KeyError:
        return template
