"""
backend/agent/advisory_prompt.py

Citizen health risk advisory generator (English + Hindi).
Features a rule-based deterministic fallback mapping based on standard CPCB bands,
source-specific recommendations, and an optional resilient LLM call with a 1.5s timeout.
"""

import json
import os

import requests

from backend.api.schemas import AdvisoryResponse
from backend.logging import logger

AQI_BANDS = [
    {
        "min": 0,
        "max": 50,
        "category_en": "Good",
        "category_hi": "अच्छा",
        "category_kn": "ಉತ್ತಮ",
        "category_ta": "நல்லது",
        "message_en": "Air quality is satisfactory, and air pollution poses little or no risk.",
        "message_hi": "वायु की गुणवत्ता संतोषजनक है, और वायु प्रदूषण से कोई या बहुत कम जोखिम है।",
        "message_kn": "ವಾಯು ಗುಣಮಟ್ಟವು ತೃಪ್ತಿಕರವಾಗಿದೆ ಮತ್ತು ಮಾಲಿನ್ಯದಿಂದ ಯಾವುದೇ ಅಪಾಯವಿಲ್ಲ.",
        "message_ta": "காற்றின் தரம் திருப்திகரமாக உள்ளது, மேலும் காற்று மாசுபாட்டால் ஆபத்து இல்லை.",
        "precautions_en": [
            "No precautions needed. Great day for outdoor activities.",
            "Keep windows open to maintain ventilation.",
        ],
        "precautions_hi": [
            "किसी सावधानी की आवश्यकता नहीं है। बाहरी गतिविधियों के लिए बहुत अच्छा दिन है।",
            "कमरों में वेंटिलेशन बनाए रखने के लिए खिड़कियाँ खुली रखें।",
        ],
        "precautions_kn": [
            "ಯಾವುದೇ ಮುನ್ನೆಚ್ಚರಿಕೆಗಳ ಅಗತ್ಯವಿಲ್ಲ. ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆಗಳಿಗೆ ಸೂಕ್ತ ದಿನ.",
            "ಉತ್ತಮ ಗಾಳಿ ಸಂಚಾರಕ್ಕಾಗಿ ಕಿಟಕಿಗಳನ್ನು ತೆರೆದಿಡಿ.",
        ],
        "precautions_ta": [
            "எந்த முன்னெச்சரிக்கை நடவடிக்கையும் தேவையில்லை. வெளி நடவடிக்கைகளுக்கு சிறந்த நாள்.",
            "காற்றோட்டத்தை பராமரிக்க ஜன்னல்களை திறந்து வைக்கவும்.",
        ],
    },
    {
        "min": 51,
        "max": 100,
        "category_en": "Satisfactory",
        "category_hi": "संतोषजनक",
        "category_kn": "ತೃಪ್ತಿಕರ",
        "category_ta": "திருப்திகரமானது",
        "message_en": "Air quality is acceptable; however, there may be a moderate concern for sensitive individuals.",
        "message_hi": "वायु की गुणवत्ता स्वीकार्य है; हालांकि, संवेदनशील लोगों के लिए हल्की चिंता हो सकती है।",
        "message_kn": "ವಾಯು ಗುಣಮಟ್ಟ ಸ್ವೀಕಾರಾರ್ಹವಾಗಿದೆ; ಸೂಕ್ಷ್ಮ ವ್ಯಕ್ತಿಗಳಿಗೆ ಸಣ್ಣ ಕಾಳಜಿ ಇರಬಹುದು.",
        "message_ta": "காற்றின் தரம் ஏற்கத்தக்கது; உணர்திறன் கொண்ட நபர்களுக்கு சிறிய கவலை இருக்கலாம்.",
        "precautions_en": [
            "Sensitive people (e.g. with asthma) should consider reducing heavy outdoor exertion.",
            "Monitor air quality changes if you suffer from respiratory issues.",
        ],
        "precautions_hi": [
            "संवेदनशील लोगों (जैसे अस्थमा से पीड़ित) को भारी बाहरी परिश्रम कम करने पर विचार करना चाहिए।",
            "यदि आप सांस की बीमारी से पीड़ित हैं, तो वायु गुणवत्ता में बदलावों पर नजर रखें।",
        ],
        "precautions_kn": [
            "ಅಸ್ತಮಾ ಪೀಡಿತ ಸೂಕ್ಷ್ಮ ವ್ಯಕ್ತಿಗಳು ಹೊರಾಂಗಣ ಶ್ರಮವನ್ನು ಕಡಿಮೆ ಮಾಡಬೇಕು.",
            "ಉಸಿರಾಟದ ತೊಂದರೆ ಇದ್ದರೆ ಗಾಳಿಯ ಗುಣಮಟ್ಟವನ್ನು ಗಮನಿಸಿ.",
        ],
        "precautions_ta": [
            "ஆஸ்துமா உள்ள உணர்திறன் கொண்ட நபர்கள் கடுமையான வெளிப்புற உழைப்பைக் குறைக்க வேண்டும்.",
            "சுவாசப் பிரச்சனைகள் இருந்தால் காற்றுத் தர மாற்றங்களைக் கண்காணிக்கவும்.",
        ],
    },
    {
        "min": 101,
        "max": 200,
        "category_en": "Moderate",
        "category_hi": "सामान्य रूप से प्रदूषित",
        "category_kn": "ಮಧ್ಯಮ",
        "category_ta": "மிதமான",
        "message_en": "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
        "message_hi": "संवेदनशील समूहों के लोगों को स्वास्थ्य प्रभाव महसूस हो सकते हैं। आम लोगों के प्रभावित होने की संभावना कम है।",
        "message_kn": "ಸೂಕ್ಷ್ಮ ಗುಂಪಿನ ಜನರಿಗೆ ಆರೋಗ್ಯದ ಮೇಲೆ ಪರಿಣಾಮ ಬೀರಬಹುದು. ಸಾಮಾನ್ಯ ಜನರಿಗೆ ಕಡಿಮೆ ಪ್ರಭಾವ.",
        "message_ta": "உணர்திறன் குழுக்களுக்கு சுகாதார பாதிப்புகள் ஏற்படலாம். பொதுமக்களுக்கு பாதிப்பு குறைவு.",
        "precautions_en": [
            "Sensitive groups should limit prolonged outdoor activities.",
            "Take more breaks during outdoor activities if symptoms arise.",
        ],
        "precautions_hi": [
            "संवेदनशील समूहों को लंबे समय तक बाहरी गतिविधियों को सीमित करना चाहिए।",
            "लक्षण उत्पन्न होने पर बाहरी गतिविधियों के दौरान अधिक विश्राम लें।",
        ],
        "precautions_kn": [
            "ಸೂಕ್ಷ್ಮ ಗುಂಪುಗಳು ದೀರ್ಘ ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆಗಳನ್ನು ಮಿತಿಗೊಳಿಸಬೇಕು.",
            "ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದರೆ ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆಗಳ ನಡುವೆ ವಿರಾಮ ತಗೆದುಕೊಳ್ಳಿ.",
        ],
        "precautions_ta": [
            "உணர்திறன் கொண்ட குழுக்கள் வெளிப்புற நடவடிக்கைகளை கட்டுப்படுத்த வேண்டும்.",
            "அறிகுறிகள் தோன்றினால் வெளிப்புற நடவடிக்கைகளின் போது ஓய்வு எடுக்கவும்.",
        ],
    },
    {
        "min": 201,
        "max": 300,
        "category_en": "Poor",
        "category_hi": "खराब",
        "category_kn": "ಕಳಪೆ",
        "category_ta": "மோசம்",
        "message_en": "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
        "message_hi": "हर किसी को स्वास्थ्य प्रभाव महसूस होना शुरू हो सकता है; संवेदनशील समूहों को अधिक गंभीर प्रभाव हो सकते हैं।",
        "message_kn": "ಎಲ್ಲರಿಗೂ ಆರೋಗ್ಯ ಸಮಸ್ಯೆಗಳು ಪ್ರಾರಂಭವಾಗಬಹುದು; ಸೂಕ್ಷ್ಮ ಗುಂಪುಗಳಿಗೆ ಹೆಚ್ಚಿನ ಅಪಾಯ.",
        "message_ta": "அனைவருக்கும் சுகாதார பாதிப்புகள் ஏற்படலாம்; உணர்திறன் குழுக்களுக்கு கடுமையான பாதிப்புகள் ஏற்படலாம்.",
        "precautions_en": [
            "Wear protective masks (N95 or equivalent) when outdoors.",
            "Avoid strenuous outdoor activities, especially children and seniors.",
            "Close windows to avoid outdoor dust and smog.",
        ],
        "precautions_hi": [
            "बाहर जाते समय सुरक्षात्मक मास्क (N95 या समकक्ष) पहनें।",
            "भारी बाहरी गतिविधियों से बचें, विशेष रूप से बच्चे और बुजुर्ग व्यक्ति।",
            "बाहरी धूल और धुंध से बचने के लिए खिड़कियाँ बंद रखें।",
        ],
        "precautions_kn": [
            "ಹೊರಗೆ ಹೋಗುವಾಗ N95 ಮಾಸ್ಕ್ ಧರಿಸಿ.",
            "ಮಕ್ಕಳು ಮತ್ತು ಹಿರಿಯರು ಹೊರಾಂಗಣ ಶ್ರಮದಾಯಕ ಚಟುವಟಿಕೆಗಳನ್ನು ತಡೆಯಿರಿ.",
            "ಧೂಳು ಮತ್ತು ಹೊಗೆಯನ್ನು ತಡೆಯಲು ಕಿಟಕಿಗಳನ್ನು ಮುಚ್ಚಿ.",
        ],
        "precautions_ta": [
            "வெளியே செல்லும்போது N95 முகக்கவசம் அணியவும்.",
            "குழந்தைகள் மற்றும் முதியவர்கள் கடுமையான வெளிப்புற நடவடிக்கைகளை தவிர்க்கவும்.",
            "தூசி மற்றும் புகையைத் தவிர்க்க ஜன்னல்களை மூடவும்.",
        ],
    },
    {
        "min": 301,
        "max": 400,
        "category_en": "Very Poor",
        "category_hi": "बहुत खराब",
        "category_kn": "ಅತ್ಯಂತ ಕಳಪೆ",
        "category_ta": "மிகவும் மோசம்",
        "message_en": "Health alert: everyone may experience more serious health effects. Immediate exposure reduction is advised.",
        "message_hi": "स्वास्थ्य चेतावनी: सभी को गंभीर स्वास्थ्य प्रभाव महसूस हो सकते हैं। बाहरी संपर्क तुरंत कम करने की सलाह दी जाती है।",
        "message_kn": "ಆರೋಗ್ಯ ಎಚ್ಚರಿಕೆ: ಪ್ರತಿಯೊಬ್ಬರಿಗೂ ತೀವ್ರ ಆರೋಗ್ಯ ಪರಿಣಾಮಗಳುಂಟಾಗಬಹುದು.",
        "message_ta": "சுகாதார எச்சரிக்கை: அனைவருக்கும் கடுமையான சுகாதார பாதிப்புகள் ஏற்படலாம்.",
        "precautions_en": [
            "Sensitive groups should remain indoors. General population should avoid outdoor activities.",
            "Wear N95 masks if outdoor travel is mandatory.",
            "Use air purifiers indoors and close all windows.",
            "Avoid burning any dry leaves or waste nearby.",
        ],
        "precautions_hi": [
            "संवेदनशील समूह घर के अंदर ही रहें। आम लोगों को बाहरी गतिविधियों से बचना चाहिए।",
            "बाहरी यात्रा अनिवार्य होने पर N95 मास्क पहनें।",
            "कमरे में एयर प्यूरीफायर चलाएं और खिड़कियाँ बंद रखें।",
            "आसपास सूखे पत्ते या कचरा जलाने से बचें।",
        ],
        "precautions_kn": [
            "ಸೂಕ್ಷ್ಮ ಗುಂಪುಗಳು ಮನೆಯೊಳಗಿರಬೇಕು. ಸಾರ್ವಜನಿಕರು ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆ ತಡೆಯಿರಿ.",
            "ಅಗತ್ಯವಿದ್ದರೆ N95 ಮಾಸ್ಕ್ ಬಳಸಿ.",
            "ಮನೆಯೊಳಗೆ ಏರ್ ಪ್ಯೂರಿಫೈಯರ್ ಬಳಸಿ.",
        ],
        "precautions_ta": [
            "உணர்திறன் குழுக்கள் வீட்டிற்குள் இருக்க வேண்டும்.",
            "வெளியே செல்ல வேண்டியிருந்தால் N95 முகக்கவசம் அணியவும்.",
            "வீட்டிற்குள் காற்று சுத்திகரிப்பான்களைப் பயன்படுத்தவும்.",
        ],
    },
    {
        "min": 401,
        "max": 9999,
        "category_en": "Severe",
        "category_hi": "गंभीर",
        "category_kn": "ತೀವ್ರ",
        "category_ta": "கடுமையான",
        "message_en": "Emergency conditions. Health warnings of emergency levels. General population is severely affected.",
        "message_hi": "आपातकालीन स्थिति। स्वास्थ्य पर गंभीर प्रभाव। आम आबादी गंभीर रूप से प्रभावित होती है।",
        "message_kn": "ತುರ್ತು ಪರಿಸ್ಥಿತಿ. ಸಾರ್ವಜನಿಕ ಆರೋಗ್ಯದ ಮೇಲೆ ಅತ್ಯಂತ ಗಂಭೀರ ಪರಿಣಾಮ.",
        "message_ta": "அவசரநிலை. பொதுமக்கள் கடுமையாக பாதிக்கப்படுகின்றனர்.",
        "precautions_en": [
            "Avoid all outdoor exertion and physical activities.",
            "General public must remain indoors. Sensitive individuals must stay in clean air rooms.",
            "Keep all windows and doors tightly shut; run indoor air purifiers continuously.",
            "Wear well-fitted N95/N99 masks if stepping out is absolutely unavoidable.",
        ],
        "precautions_hi": [
            "सभी प्रकार के बाहरी शारीरिक परिश्रम और गतिविधियों से बचें।",
            "आम जनता घर के अंदर ही रहे। संवेदनशील लोग साफ हवा वाले कमरों में रहें।",
            "सभी खिड़कियाँ और दरवाजे कसकर बंद रखें; कमरे में लगातार एयर प्यूरीफायर चलाएं।",
            "यदि बाहर जाना बिल्कुल अपरिहार्य हो तो फिटेड N95/N99 मास्क पहनें।",
        ],
        "precautions_kn": [
            "ಎಲ್ಲಾ ಹೊರಾಂಗಣ ಶ್ರಮದಾಯಕ ಚಟುವಟಿಕೆಗಳನ್ನು ತಡೆಯಿರಿ.",
            "ಸಾಮಾನ್ಯ ಜನರು ಮನೆಯೊಳಗೇ ಇರಬೇಕು.",
            "N95/N99 ಮಾಸ್ಕ್ ಕಡ್ಡಾಯವಾಗಿ ಬಳಸಿ.",
        ],
        "precautions_ta": [
            "அனைத்து வெளிப்புற உடற்பயிற்சிகளையும் தவிர்க்கவும்.",
            "பொதுமக்கள் வீட்டிற்குள் இருக்க வேண்டும்.",
            "N95/N99 முகக்கவசங்களைப் பயன்படுத்தவும்.",
        ],
    },
]

SOURCE_PRECAUTIONS = {
    "agricultural_burning": {
        "en": "Avoid areas downwind of agricultural fields/stubble burning to prevent acute smoke inhalation.",
        "hi": "तीव्र धुएँ के सांस में जाने से बचने के लिए फसल अवशेष जलाने वाली जगहों से अनुकूल हवा की दिशा में जाने से बचें।",
        "kn": "ಕೃಷಿ ತ್ಯಾಜ್ಯ ಸುಡುವ ಪ್ರದೇಶಗಳಿಂದ ಬರುವ ಹೊಗೆಯನ್ನು ತಡೆಯಲು ಗಾಳಿಯ ದಿಕ್ಕನ್ನು ಗಮನಿಸಿ.",
        "ta": "விவசாயக் கழிவுகள் எரிக்கும் இடங்களிலிருந்து வரும் புகையைத் தவிர்க்க காற்றின் திசையைக் கவனிக்கவும்.",
    },
    "traffic": {
        "en": "Avoid walking or exercising near high-traffic corridors during peak commute hours.",
        "hi": "भीड़भाड़ वाले समय में व्यस्त सड़कों या मुख्य मार्गों के पास टहलने या व्यायाम करने से बचें।",
        "kn": "ಹೆಚ್ಚು ವಾಹನ ದಟ್ಟಣೆ ಇರುವ ಸಮಯಗಳಲ್ಲಿ ರಸ್ತೆಗಳ ಬಳಿ ವಾಯುವಿಹಾರ ತಡೆಯಿರಿ.",
        "ta": "அதிக போக்குவரத்து நெரிசல் உள்ள நேரங்களில் நடைபயிற்சியைத் தவிர்க்கவும்.",
    },
    "industrial": {
        "en": "Ensure indoor ventilation systems have high-efficiency particulate air (HEPA) filters if near industrial zones.",
        "hi": "औद्योगिक क्षेत्रों के पास होने पर इनडोर वेंटिलेशन सिस्टम में उच्च दक्षता वाले कण हवा (HEPA) फिल्टर लगाना सुनिश्चित करें।",
        "kn": " ಕೈಗಾರಿಕಾ ಪ್ರದೇಶಗಳ ಬಳಿ ಹೆಪಾ (HEPA) ಫಿಲ್ಟರ್‌ಗಳನ್ನು ಬಳಸಿ.",
        "ta": "தொழில்துறை பகுதிகளுக்கு அருகில் HEPA வடிகட்டிகளைப் பயன்படுத்தவும்.",
    },
}


def get_deterministic_advisory(
    current_aqi: float,
    primary_cause: str,
    language: str,
) -> AdvisoryResponse:
    """
    Returns a rule-based citizen advisory matching the AQI band and primary cause.
    Supports English ('en'), Hindi ('hi'), Kannada ('kn'), and Tamil ('ta').
    """
    lang = language.lower()
    if lang not in ("en", "hi", "kn", "ta"):
        lang = "en"

    # Find matching AQI band
    band = AQI_BANDS[-1]
    for b in AQI_BANDS:
        if b["min"] <= current_aqi <= b["max"]:
            band = b
            break

    category = band.get(f"category_{lang}", band["category_en"])
    message = band.get(f"message_{lang}", band["message_en"])
    precautions = list(band.get(f"precautions_{lang}", band["precautions_en"]))

    if primary_cause in SOURCE_PRECAUTIONS:
        src_msg = SOURCE_PRECAUTIONS[primary_cause].get(lang, SOURCE_PRECAUTIONS[primary_cause]["en"])
        precautions.append(src_msg)

    return AdvisoryResponse(
        aqi_category=category,
        health_message=message,
        recommended_precautions=precautions,
        language=lang,
        llm_error=False,
    )


def generate_llm_advisory(
    current_aqi: float,
    forecasted_aqi: float,
    primary_cause: str,
    language: str,
) -> tuple[AdvisoryResponse, bool]:
    """
    Makes a 1.5s timeout API call to request a localized LLM-generated health advisory.
    Parses structural output into an AdvisoryResponse.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    if not api_key:
        raise ValueError("Missing API key")

    lang_name = "Hindi" if language.lower() == "hi" else "English"
    cause_desc = {
        "agricultural_burning": "agricultural stubble burning smoke transport",
        "traffic": "vehicular emissions and road dust in heavy traffic",
        "industrial": "continuous industrial manufacturing stack emissions",
    }.get(primary_cause, primary_cause)

    forecast_str = (
        f"{forecasted_aqi:.0f}" if forecasted_aqi is not None else "Not Available"
    )

    # Prompt request
    prompt = f"""You are a professional public health official generating an official city air quality advisory in {lang_name}.
    Based on the following data, write a tailored advisory response.

    DATA:
    - Current Measured AQI: {current_aqi:.0f}
    - 24-Hour Forecast AQI: {forecast_str}
    - Primary Pollution Source: {cause_desc}

    OUTPUT FORMAT:
    You must respond in raw JSON format with the following keys. Do not include any markdown fences or additional text:
    {{
        "category": "A short 1-3 word severity band matching this AQI (e.g. Good, Poor, Severe)",
        "message": "A concise 1-2 sentence health warning summarizing who is at risk and general guidance.",
        "precautions": [
            "A list of 3-4 specific, actionable precaution bullets. Integrate advice related to the pollution source ({cause_desc}) if relevant."
        ]
    }}

    The values of the keys must be translated completely into {lang_name}."""

    # Normalize url
    api_base = api_base.rstrip("/")
    if "nvidia" not in api_base.lower() and not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"
    url = f"{api_base}/chat/completions"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    model = (
        "meta/llama-3.1-405b-instruct"
        if "nvidia" in api_base.lower()
        else "gpt-3.5-turbo"
    )
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500,
        "response_format": (
            {"type": "json_object"} if "nvidia" not in api_base.lower() else None
        ),
    }

    response = requests.post(url, headers=headers, json=data, timeout=1.5)
    if response.status_code == 200:
        res_json = response.json()
        content = res_json["choices"][0]["message"]["content"].strip()

        # Clean up any potential markdown code fences from model
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        parsed = json.loads(content)

        return (
            AdvisoryResponse(
                aqi_category=parsed["category"],
                health_message=parsed["message"],
                recommended_precautions=parsed["precautions"],
                language=language,
                llm_error=False,
            ),
            False,
        )
    else:
        raise RuntimeError(f"HTTP Error {response.status_code}: {response.text}")


def generate_advisory(
    current_aqi: float,
    forecasted_aqi: float = None,
    primary_cause: str = "traffic",
    language: str = "en",
    enable_llm: bool = True,
) -> AdvisoryResponse:
    """
    Orchestrator for generating citizen advisories. Tries LLM generation
    with a strict timeout, falling back gracefully to CPCB rule-based advisory
    on any errors or if LLM is disabled.
    """
    if enable_llm:
        try:
            advisory, has_error = generate_llm_advisory(
                current_aqi, forecasted_aqi, primary_cause, language
            )
            if not has_error:
                return advisory
        except Exception as e:
            logger.error(
                f"LLM advisory generation failed: {e}. Falling back to deterministic template."
            )

    # Fallback to deterministic CPCB rule-based template
    advisory = get_deterministic_advisory(current_aqi, primary_cause, language)
    advisory.llm_error = (
        enable_llm  # Marks as true if LLM was requested but failed/timed out
    )
    return advisory
