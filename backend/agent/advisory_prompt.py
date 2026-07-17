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
        "message_en": "Air quality is satisfactory, and air pollution poses little or no risk.",
        "message_hi": "वायु की गुणवत्ता संतोषजनक है, और वायु प्रदूषण से कोई या बहुत कम जोखिम है।",
        "precautions_en": [
            "No precautions needed. Great day for outdoor activities.",
            "Keep windows open to maintain ventilation.",
        ],
        "precautions_hi": [
            "किसी सावधानी की आवश्यकता नहीं है। बाहरी गतिविधियों के लिए बहुत अच्छा दिन है।",
            "कमरों में वेंटिलेशन बनाए रखने के लिए खिड़कियाँ खुली रखें।",
        ],
    },
    {
        "min": 51,
        "max": 100,
        "category_en": "Satisfactory",
        "category_hi": "संतोषजनक",
        "message_en": "Air quality is acceptable; however, there may be a moderate concern for sensitive individuals.",
        "message_hi": "वायु की गुणवत्ता स्वीकार्य है; हालांकि, संवेदनशील लोगों के लिए हल्की चिंता हो सकती है।",
        "precautions_en": [
            "Sensitive people (e.g. with asthma) should consider reducing heavy outdoor exertion.",
            "Monitor air quality changes if you suffer from respiratory issues.",
        ],
        "precautions_hi": [
            "संवेदनशील लोगों (जैसे अस्थमा से पीड़ित) को भारी बाहरी परिश्रम कम करने पर विचार करना चाहिए।",
            "यदि आप सांस की बीमारी से पीड़ित हैं, तो वायु गुणवत्ता में बदलावों पर नजर रखें।",
        ],
    },
    {
        "min": 101,
        "max": 200,
        "category_en": "Moderate",
        "category_hi": "सामान्य रूप से प्रदूषित",
        "message_en": "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
        "message_hi": "संवेदनशील समूहों के लोगों को स्वास्थ्य प्रभाव महसूस हो सकते हैं। आम लोगों के प्रभावित होने की संभावना कम है।",
        "precautions_en": [
            "Sensitive groups should limit prolonged outdoor activities.",
            "Take more breaks during outdoor activities if symptoms arise.",
        ],
        "precautions_hi": [
            "संवेदनशील समूहों को लंबे समय तक बाहरी गतिविधियों को सीमित करना चाहिए।",
            "लक्षण उत्पन्न होने पर बाहरी गतिविधियों के दौरान अधिक विश्राम लें।",
        ],
    },
    {
        "min": 201,
        "max": 300,
        "category_en": "Poor",
        "category_hi": "खराब",
        "message_en": "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
        "message_hi": "हर किसी को स्वास्थ्य प्रभाव महसूस होना शुरू हो सकता है; संवेदनशील समूहों को अधिक गंभीर प्रभाव हो सकते हैं।",
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
    },
    {
        "min": 301,
        "max": 400,
        "category_en": "Very Poor",
        "category_hi": "बहुत खराब",
        "message_en": "Health alert: everyone may experience more serious health effects. Immediate exposure reduction is advised.",
        "message_hi": "स्वास्थ्य चेतावनी: सभी को गंभीर स्वास्थ्य प्रभाव महसूस हो सकते हैं। बाहरी संपर्क तुरंत कम करने की सलाह दी जाती है।",
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
    },
    {
        "min": 401,
        "max": 9999,
        "category_en": "Severe",
        "category_hi": "गंभीर",
        "message_en": "Emergency conditions. Health warnings of emergency levels. General population is severely affected.",
        "message_hi": "आपातकालीन स्थिति। स्वास्थ्य पर गंभीर प्रभाव। आम आबादी गंभीर रूप से प्रभावित होती है।",
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
    },
]

SOURCE_PRECAUTIONS = {
    "agricultural_burning": {
        "en": "Avoid areas downwind of agricultural fields/stubble burning to prevent acute smoke inhalation.",
        "hi": "तीव्र धुएँ के सांस में जाने से बचने के लिए फसल अवशेष जलाने वाली जगहों से अनुकूल हवा की दिशा में जाने से बचें।",
    },
    "traffic": {
        "en": "Avoid walking or exercising near high-traffic corridors during peak commute hours.",
        "hi": "भीड़भाड़ वाले समय में व्यस्त सड़कों या मुख्य मार्गों के पास टहलने या व्यायाम करने से बचें।",
    },
    "industrial": {
        "en": "Ensure indoor ventilation systems have high-efficiency particulate air (HEPA) filters if near industrial zones.",
        "hi": "औद्योगिक क्षेत्रों के पास होने पर इनडोर वेंटिलेशन सिस्टम में उच्च दक्षता वाले कण हवा (HEPA) फिल्टर लगाना सुनिश्चित करें।",
    },
}


def get_deterministic_advisory(
    current_aqi: float,
    primary_cause: str,
    language: str,
) -> AdvisoryResponse:
    """
    Returns a rule-based citizen advisory matching the AQI band and primary cause.
    """
    lang = language.lower()
    if lang not in ("en", "hi"):
        lang = "en"

    # Find matching AQI band
    band = AQI_BANDS[-1]
    for b in AQI_BANDS:
        if b["min"] <= current_aqi <= b["max"]:
            band = b
            break

    if lang == "hi":
        category = band["category_hi"]
        message = band["message_hi"]
        precautions = list(band["precautions_hi"])
        # Add source specific precaution if available
        if primary_cause in SOURCE_PRECAUTIONS:
            precautions.append(SOURCE_PRECAUTIONS[primary_cause]["hi"])
    else:
        category = band["category_en"]
        message = band["message_en"]
        precautions = list(band["precautions_en"])
        if primary_cause in SOURCE_PRECAUTIONS:
            precautions.append(SOURCE_PRECAUTIONS[primary_cause]["en"])

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
