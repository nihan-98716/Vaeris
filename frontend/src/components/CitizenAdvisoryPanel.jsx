/**
 * frontend/src/components/CitizenAdvisoryPanel.jsx
 *
 * Citizen Health Risk Advisory Panel (English, Hindi, Kannada, Tamil).
 * Displays AQI severity category, health warnings, and recommended precautions.
 * Instant zero-latency multi-language translation (EN, HI, KN, TA).
 */

import { useState, useEffect } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';

// ─── Local Multilingual Database Fallback ──────────────────────────────────────

const LOCAL_AQI_BANDS = [
  {
    min: 0,
    max: 50,
    category: { en: "Good", hi: "अच्छा", kn: "ಉತ್ತಮ", ta: "நன்று" },
    message: {
      en: "Air quality is satisfactory, and air pollution poses little or no risk.",
      hi: "वायु की गुणवत्ता संतोषजनक है, और वायु प्रदूषण से कोई या बहुत कम जोखिम है।",
      kn: "ಗಾಳಿಯ ಗುಣಮಟ್ಟ ತೃಪ್ತಿಕರವಾಗಿದೆ, ಮತ್ತು ವಾಯು ಮಾಲಿನ್ಯವು ಕಡಿಮೆ ಅಥವಾ ಯಾವುದೇ ಅಪಾಯವನ್ನುಂಟುಮಾಡುವುದಿಲ್ಲ.",
      ta: "காற்றின் தரம் திருப்திகரமாக உள்ளது, மேலும் காற்று மாசுபாடு குறைந்த அல்லது ஆபத்தை ஏற்படுத்தாது."
    },
    precautions: {
      en: ["No precautions needed. Great day for outdoor activities.", "Keep windows open to maintain ventilation."],
      hi: ["किसी सावधानी की आवश्यकता नहीं है। बाहरी गतिविधियों के लिए बहुत अच्छा दिन है।", "कमरों में वेंटिलेशन बनाए रखने के लिए खिड़कियाँ खुली रखें।"],
      kn: ["ಯಾವ ಮುನ್ನೆಚ್ಚರಿಕೆಯ ಅಗತ್ಯವಿಲ್ಲ. ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆಗಳಿಗೆ ಉತ್ತಮ ದಿನ.", "ಗಾಳಿ ಸಂಚಾರಕ್ಕಾಗಿ ಕಿಟಕಿಗಳನ್ನು ತೆರೆದಿಡಿ."],
      ta: ["முன்னெச்சரிக்கைகள் தேவையில்லை. வெளிப்புற நடவடிக்கைகளுக்கு சிறந்த நாள்.", "காற்றோட்டத்தை பராமரிக்க ஜன்னல்களை திறந்து வைக்கவும்."]
    }
  },
  {
    min: 51,
    max: 100,
    category: { en: "Satisfactory", hi: "संतोषजनक", kn: "ತೃಪ್ತಿಕರ", ta: "திருப்திகரம்" },
    message: {
      en: "Air quality is acceptable; however, there may be a moderate concern for sensitive individuals.",
      hi: "वायु की गुणवत्ता स्वीकार्य है; हालांकि, संवेदनशील लोगों के लिए हल्की चिंता हो सकती है।",
      kn: "ಗಾಳಿಯ ಗುಣಮಟ್ಟ ಸ್ವೀಕಾರಾರ್ಹವಾಗಿದೆ; ಆದಾಗ್ಯೂ ಸೂಕ್ಷ್ಮ ವ್ಯಕ್ತಿಗಳಿಗೆ ಸ್ವಲ್ಪ ಕಾಳಜಿ ಇರಬಹುದು.",
      ta: "காற்றின் தரம் ஏற்றுக்கொள்ளத்தக்கது; இருப்பினும், உணர்திறன் கொண்ட நபர்களுக்கு மிதமான கவலை இருக்கலாம்."
    },
    precautions: {
      en: ["Sensitive individuals should consider reducing heavy outdoor exertion.", "Monitor air quality changes if you suffer from respiratory issues."],
      hi: ["संवेदनशील लोगों को भारी बाहरी परिश्रम कम करने पर विचार करना चाहिए।", "यदि आप सांस की बीमारी से पीड़ित हैं, तो वायु गुणवत्ता में बदलावों पर नजर रखें।"],
      kn: ["ಸೂಕ್ಷ್ಮ ವ್ಯಕ್ತಿಗಳು ಹೊರಾಂಗಣ ಶ್ರಮವನ್ನು ಕಡಿಮೆ ಮಾಡುವುದನ್ನು ಪರಿಗಣಿಸಬೇಕು.", "ಉಸಿರಾಟದ ತೊಂದರೆ ಇದ್ದರೆ ಗಾಳಿಯ ಗುಣಮಟ್ಟವನ್ನು ಗಮನಿಸಿ."],
      ta: ["உணர்திறன் கொண்ட நபர்கள் வெளிப்புற உடற்பயிற்சியைக் குறைக்க வேண்டும்.", "உடலநலப் பிரச்சினைகள் இருந்தால் காற்றின் தரத்தைக் கண்காணிக்கவும்."]
    }
  },
  {
    min: 101,
    max: 200,
    category: { en: "Moderate", hi: "सामान्य रूप से प्रदूषित", kn: "ಮಿಶ್ರಣ", ta: "மிதமான" },
    message: {
      en: "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
      hi: "संवेदनशील समूहों के लोगों को स्वास्थ्य प्रभाव महसूस हो सकते हैं। आम लोगों के प्रभावित होने की संभावना कम है।",
      kn: "ಸೂಕ್ಷ್ಮ ಗುಂಪುಗಳ ಸದಸ್ಯರು ಆರೋಗ್ಯ ಪರಿಣಾಮಗಳನ್ನು ಅನುಭವಿಸಬಹುದು.",
      ta: "உணர்திறன் கொண்ட குழுக்களின் உறுப்பினர்கள் சுகாதார பாதிப்புகளை சந்திக்கலாம்."
    },
    precautions: {
      en: ["Sensitive groups should limit prolonged outdoor activities.", "Take breaks during outdoor exertion."],
      hi: ["संवेदनशील समूहों को लंबे समय तक बाहरी गतिविधियों को सीमित करना चाहिए।", "बाहरी गतिविधियों के दौरान विश्राम लें।"],
      kn: ["ಸೂಕ್ಷ್ಮ ಗುಂಪುಗಳು ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆಗಳನ್ನು ಮಿತಿಗೊಳಿಸಬೇಕು.", "ಹೊರಾಂಗಣ ಚಟುವಟಿಕೆಗಳ ಸಮಯದಲ್ಲಿ ವಿರಾಮ ತೆಗೆದುಕೊಳ್ಳಿ."],
      ta: ["உணர்திறன் கொண்ட குழுக்கள் வெளிப்புற நடவடிக்கைகளைக் கட்டுப்படுத்த வேண்டும்.", "வெளிப்புற பயிற்சியின் போது இடைவேளை எடுக்கவும்."]
    }
  },
  {
    min: 201,
    max: 300,
    category: { en: "Poor", hi: "खराब", kn: "ಕಳಪೆ", ta: "மோசம்" },
    message: {
      en: "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
      hi: "हर किसी को स्वास्थ्य प्रभाव महसूस होना शुरू हो सकता है; संवेदनशील समूहों को अधिक गंभीर प्रभाव हो सकते हैं।",
      kn: "ಗಾಳಿಯ ಗುಣಮಟ್ಟ ಕಳಪೆಯಾಗಿದೆ. ಸೂಕ್ಷ್ಮ ವ್ಯಕ್ತಿಗಳು ಹೊರಾಂಗಣ ಶ್ರಮವನ್ನು ಕಡಿಮೆ ಮಾಡಬೇಕು.",
      ta: "காற்றின் தரம் மோசமாக உள்ளது. உணர்திறன் கொண்ட நபர்கள் வெளிப்புற உடற்பயிற்சியைக் குறைக்க வேண்டும்."
    },
    precautions: {
      en: ["Limit outdoor exercise during peak pollution hours.", "Wear an N95 mask if traveling along busy traffic corridors.", "Keep indoor windows closed when outside air feels smoky."],
      hi: ["प्रदूषण के चरम घंटों के दौरान बाहरी व्यायाम सीमित करें।", "व्यस्त यातायात गलियारों में यात्रा करते समय N95 मास्क पहनें।", "जब बाहर हवा धुएँदार महसूस हो तो घर की खिड़कियाँ बंद रखें।"],
      kn: ["ಗರಿಷ್ಠ ಮಾಲಿನ್ಯದ ಅವಧಿಯಲ್ಲಿ ಹೊರಾಂಗಣ ವ್ಯಾಯಾಮವನ್ನು ಮಿತಿಗೊಳಿಸಿ.", "ನಿರತ ಸಂಚಾರ ಮಾರ್ಗಗಳಲ್ಲಿ ಪ್ರಯಾಣಿಸುವಾಗ N95 ಮಾಸ್ಕ್ ಧರಿಸಿ.", "ಹೊರಗಿನ ಗಾಳಿಯು ಹೊಗೆಯಿಂದ ಕೂಡಿದಾಗ ಮನೆಯ ಕಿಟಕಿಗಳನ್ನು ಮುಚ್ಚಿಡಿ."],
      ta: ["அதிக மாசு நேரங்களில் வெளிப்புற உடற்பயிற்சியைக் கட்டுப்படுத்தவும்.", "பரபரப்பான போக்குவரத்து பாதைகளில் பயணிக்கும் போது N95 மாஸ்க் அணியவும்.", "வெளியே புகை மூட்டமாக இருக்கும் போது வீட்டு ஜன்னல்களை மூடி வைக்கவும்."]
    }
  },
  {
    min: 301,
    max: 400,
    category: { en: "Very Poor", hi: "बहुत खराब", kn: "ಬಹಳ ಕಳಪೆ", ta: "மிகவும் மோசம்" },
    message: {
      en: "Health alert: everyone may experience more serious health effects. Immediate exposure reduction is advised.",
      hi: "स्वास्थ्य चेतावनी: सभी को गंभीर स्वास्थ्य प्रभाव महसूस हो सकते हैं। बाहरी संपर्क तुरंत कम करने की सलाह दी जाती है।",
      kn: "ಆರೋಗ್ಯ ಎಚ್ಚರಿಕೆ: ಪ್ರತಿಯೊಬ್ಬರೂ ಹೆಚ್ಚು ತೀವ್ರವಾದ ಆರೋಗ್ಯ ಪರಿಣಾಮಗಳನ್ನು ಅನುಭವಿಸಬಹುದು.",
      ta: "சுகாதார எச்சரிக்கை: அனைவரும் மிகவும் கடுமையான சுகாதார விளைவுகளை சந்திக்க நேரிடும்."
    },
    precautions: {
      en: ["Sensitive groups should remain indoors. General population should avoid outdoor activities.", "Wear N95 masks if outdoor travel is mandatory.", "Use air purifiers indoors and close all windows.", "Avoid burning any dry leaves or waste nearby."],
      hi: ["संवेदनशील समूह घर के अंदर ही रहें। आम लोगों को बाहरी गतिविधियों से बचना चाहिए।", "बाहरी यात्रा अनिवार्य होने पर N95 मास्क पहनें।", "कमरे में एयर प्यूरीफायर चलाएं और खिड़कियाँ बंद रखें।", "आसपास सूखे पत्ते या कचरा जलाने से बचें।"],
      kn: ["ಸೂಕ್ಷ್ಮ ಗುಂಪುಗಳು ಮನೆಯೊಳಗೆ ಇರಬೇಕು.", "ಹೊರಾಂಗಣ ಪ್ರಯಾಣ ಕಡ್ಡಾಯವಾಗಿದ್ದರೆ N95 ಮಾಸ್ಕ್ ಧರಿಸಿ.", "ಮನೆಯೊಳಗೆ ಏರ್ ಪ್ಯೂರಿಫೈಯರ್ ಬಳಸಿ.", "ಕಸ ಸುಡುವುದನ್ನು ತಡೆಯಿರಿ."],
      ta: ["உணர்திறன் கொண்ட குழுக்கள் வீட்டிற்குள் இருக்க வேண்டும்.", "வெளிப்புற பயணம் கட்டாயமாக இருந்தால் N95 மாஸ்க் அணியுங்கள்.", "வீட்டு காற்று சுத்திகரிப்பான்களைப் பயன்படுத்தவும்.", "குப்பைகளை எரிப்பதைத் தவிர்க்கவும்."]
    }
  },
  {
    min: 401,
    max: 9999,
    category: { en: "Severe", hi: "गंभीर", kn: "ಗಂಭೀರ", ta: "கடும்" },
    message: {
      en: "Emergency conditions. Health warnings of emergency levels. General population is severely affected.",
      hi: "आपातकालीन स्थिति। स्वास्थ्य पर गंभीर प्रभाव। आम आबादी गंभीर रूप से प्रभावित होती है।",
      kn: "ತುರ್ತು ಪರಿಸ್ಥಿತಿಗಳು. ಗಂಭೀರ ಆರೋಗ್ಯ ಪರಿಣಾಮಗಳು.",
      ta: "அவசர நிலைகள். கடுமையான சுகாதார பாதிப்புகள்."
    },
    precautions: {
      en: ["Avoid all outdoor exertion and physical activities.", "General public must remain indoors. Sensitive individuals must stay in clean air rooms.", "Keep all windows and doors tightly shut; run indoor air purifiers continuously.", "Wear well-fitted N95/N99 masks if stepping out is absolutely unavoidable."],
      hi: ["सभी प्रकार के बाहरी शारीरिक परिश्रम और गतिविधियों से बचें।", "आम जनता घर के अंदर ही रहे। संवेदनशील लोग साफ हवा वाले कमरों में रहें।", "सभी खिड़कियाँ और दरवाजे कसकर बंद रखें; कमरे में लगातार एयर प्यूरीफायर चलाएं।", "यदि बाहर जाना बिल्कुल अपरिहार्य हो तो फिटेड N95/N99 मास्क पहनें।"],
      kn: ["ಎಲ್ಲಾ ಹೊರಾಂಗಣ ಶ್ರಮವನ್ನು ತಪ್ಪಿಸಿ.", "ಸಾರ್ವಜನಿಕರು ಮನೆಯೊಳಗೆ ಇರಬೇಕು.", "ಕಿಟಕಿಗಳನ್ನು ಮುಚ್ಚಿಡಿ.", "N95 ಮಾಸ್ಕ್ ಧರಿಸಿ."],
      ta: ["அனைத்து வெளிப்புற உடற்பயிற்சிகளையும் தவிர்க்கவும்.", "பொதுமக்கள் வீட்டிற்குள் இருக்க வேண்டும்.", "ஜன்னல்களை மூடி வைக்கவும்.", "N95 மாஸ்க் அணியுங்கள்."]
    }
  }
];

const LOCAL_SOURCE_PRECAUTIONS = {
  agricultural_burning: {
    en: "Avoid areas downwind of agricultural fields/stubble burning to prevent acute smoke inhalation.",
    hi: "तीव्र धुएँ के सांस में जाने से बचने के लिए फसल अवशेष जलाने वाली जगहों से अनुकूल हवा की दिशा में जाने से बचें।",
    kn: "ತೀವ್ರ ಹೊಗೆಯನ್ನು ತಡೆಗಟ್ಟಲು ಕೃಷಿ ಸುಡುವ ಪ್ರದೇಶಗಳಿಂದ ದೂರವಿರಿ.",
    ta: "புகையை சுவாசிப்பதைத் தவிர்க்க விவசாய நிலங்களில் இருந்து தள்ளி இருங்கள்."
  },
  traffic: {
    en: "Avoid walking or exercising near high-traffic corridors during peak commute hours.",
    hi: "भीड़भाड़ वाले समय में व्यस्त सड़कों या मुख्य मार्गों के पास टहलने या व्यायाम करने से बचें।",
    kn: "ಸಂಚಾರ ಗರಿಷ್ಠ ಅವಧಿಯಲ್ಲಿ ರಸ್ತೆಬದಿಯ ವ್ಯಾಯಾಮವನ್ನು ತಪ್ಪಿಸಿ.",
    ta: "அதிக போக்குவரத்து நேரங்களில் சாலை யோரம் நடப்பதை தவிர்க்கவும்."
  },
  industrial: {
    en: "Ensure indoor ventilation systems have high-efficiency particulate air (HEPA) filters if near industrial zones.",
    hi: "औद्योगिक क्षेत्रों के पास होने पर इनडोर वेंटिलेशन सिस्टम में उच्च दक्षता वाले कण हवा (HEPA) फिल्टर लगाना सुनिश्चित करें।",
    kn: "ಔದ್ಯೋಗಿಕ ವಲಯದ ಬಳಿ ಇದ್ದರೆ HEPA ಫಿಲ್ಟರ್ ಬಳಸಿ.",
    ta: "தொழில்துறை மண்டலங்களுக்கு அருகில் இருந்தால் HEPA ஃபில்டர்களை பயன்படுத்தவும்."
  }
};

function getAqiStyle(aqi) {
  if (aqi <= 50)  return { color: 'var(--aqi-good)', bg: 'rgba(110, 231, 168, 0.08)' };
  if (aqi <= 100) return { color: 'var(--aqi-satisfactory)', bg: 'rgba(168, 217, 110, 0.08)' };
  if (aqi <= 200) return { color: 'var(--aqi-moderate)', bg: 'rgba(232, 210, 110, 0.08)' };
  if (aqi <= 300) return { color: 'var(--aqi-poor)', bg: 'rgba(232, 168, 79, 0.08)' };
  if (aqi <= 400) return { color: 'var(--aqi-very-poor)', bg: 'rgba(232, 101, 79, 0.08)' };
  return { color: 'var(--aqi-severe)', bg: 'rgba(122, 46, 61, 0.12)' };
}

function getAdvisoryForLang(lang, aqi, src) {
  let band = LOCAL_AQI_BANDS[LOCAL_AQI_BANDS.length - 1];
  for (let b of LOCAL_AQI_BANDS) {
    if (aqi >= b.min && aqi <= b.max) {
      band = b;
      break;
    }
  }

  let category = band.category[lang] || band.category.en;
  let message = band.message[lang] || band.message.en;
  let precautions = band.precautions[lang] ? [...band.precautions[lang]] : [...band.precautions.en];

  if (LOCAL_SOURCE_PRECAUTIONS[src]) {
    const extra = LOCAL_SOURCE_PRECAUTIONS[src][lang] || LOCAL_SOURCE_PRECAUTIONS[src].en;
    precautions.push(extra);
  }

  return { category, message, precautions };
}

export default function CitizenAdvisoryPanel({ currentAqi, primaryCause, forecastAqi, apiBase }) {
  const [language, setLanguage] = useState('en'); // 'en' | 'hi' | 'kn' | 'ta'

  const baselineAqi = Math.round(currentAqi || 300);
  const forecastVal = forecastAqi ? Math.round(forecastAqi) : null;
  const source      = primaryCause || 'traffic';
  const aqiStyle    = getAqiStyle(baselineAqi);

  const [advisory, setAdvisory] = useState(() => getAdvisoryForLang('en', baselineAqi, source));

  // Update advisory instantly when language, baselineAqi, or source changes
  useEffect(() => {
    // Synchronous instant update
    setAdvisory(getAdvisoryForLang(language, baselineAqi, source));

    let isMounted = true;
    async function fetchAdvisory() {
      try {
        const url =
          `${apiBase}/api/v1/advisory` +
          `?current_aqi=${baselineAqi}` +
          (forecastVal ? `&forecasted_aqi=${forecastVal}` : '') +
          `&primary_cause=${source}` +
          `&language=${language}`;

        const res = await fetch(url, { signal: AbortSignal.timeout(1200) });
        if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
        const data = await res.json();

        if (isMounted) {
          setAdvisory({
            category: data.aqi_category,
            message: data.health_message,
            precautions: data.recommended_precautions,
          });
        }
      } catch (err) {
        // Keep synchronous translation fallback
      }
    }

    fetchAdvisory();

    return () => {
      isMounted = false;
    };
  }, [baselineAqi, forecastVal, source, language, apiBase]);

  const handleLanguageChange = (langCode) => {
    setLanguage(langCode);
    setAdvisory(getAdvisoryForLang(langCode, baselineAqi, source));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={18} color="var(--color-primary)" />
          <div>
            <h2 style={{ fontSize: '15px', fontWeight: 700 }}>Citizen Health Risk Advisory</h2>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Actionable public health precautions & exposure reduction guidance</p>
          </div>
        </div>

        {/* Language selector toggle (EN, HI, KN, TA) */}
        <div className="glass-panel" style={{ padding: '4px', display: 'flex', gap: '4px', borderRadius: '8px' }}>
          {[
            { code: 'en', label: 'EN' },
            { code: 'hi', label: 'हिंदी' },
            { code: 'kn', label: 'ಕನ್ನಡ' },
            { code: 'ta', label: 'தமிழ்' }
          ].map((item) => (
            <button
              key={item.code}
              onClick={() => handleLanguageChange(item.code)}
              style={{
                padding: '5px 12px',
                borderRadius: '6px',
                border: language === item.code ? '1px solid rgba(0, 240, 255, 0.4)' : '1px solid transparent',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: language === item.code ? 700 : 500,
                background: language === item.code ? 'rgba(0, 240, 255, 0.15)' : 'transparent',
                color: language === item.code ? '#fff' : 'var(--text-muted)',
                transition: 'all 0.2s',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main advisory grid */}
      {advisory && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
          
          {/* Left AQI Severity Card */}
          <div
            className="glass-panel"
            style={{
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              justify: 'center',
              alignItems: 'center',
              gap: '12px',
              background: advisory.category ? aqiStyle.bg : 'rgba(255,255,255,0.02)',
              border: `1px solid ${aqiStyle.color}30`,
              borderRadius: '12px',
            }}
          >
            <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.5px' }}>
              SEVERITY LEVEL
            </span>
            <div
              style={{
                fontSize: '22px',
                fontWeight: 900,
                color: aqiStyle.color,
                textTransform: 'uppercase',
                textAlign: 'center'
              }}
            >
              {advisory.category}
            </div>

            <div style={{ display: 'flex', gap: '16px', marginTop: '8px' }}>
              <div style={{ textAlign: 'center' }}>
                <span style={{ fontSize: '9px', color: 'var(--text-muted)', display: 'block' }}>BASELINE AQI</span>
                <span style={{ fontSize: '20px', fontWeight: 800, color: aqiStyle.color }}>{baselineAqi}</span>
              </div>
              {forecastVal && (
                <div style={{ textAlign: 'center', borderLeft: '1px solid var(--border-light)', paddingLeft: '16px' }}>
                  <span style={{ fontSize: '9px', color: 'var(--text-muted)', display: 'block' }}>24H FORECAST</span>
                  <span style={{ fontSize: '20px', fontWeight: 800, color: getAqiStyle(forecastVal).color }}>{forecastVal}</span>
                </div>
              )}
            </div>

            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', textAlign: 'center' }}>
              Dominant Cause: <strong style={{ color: '#fff' }}>{source.replace('_', ' ').toUpperCase()}</strong>
            </div>
          </div>

          {/* Right Precautions & Message Box */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            
            {/* Health Message Alert Banner */}
            <div
              className="glass-panel"
              style={{
                padding: '16px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                borderLeft: `4px solid ${aqiStyle.color}`,
                borderRadius: '8px',
              }}
            >
              <AlertTriangle size={18} color={aqiStyle.color} style={{ flexShrink: 0, marginTop: '2px' }} />
              <p style={{ fontSize: '12.5px', color: '#fff', lineHeight: 1.5, fontWeight: 500 }}>
                {advisory.message}
              </p>
            </div>

            {/* Recommended Precautions List */}
            <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-primary)', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={14} color="var(--color-primary)" />
                <span>RECOMMENDED PUBLIC HEALTH PRECAUTIONS</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {advisory.precautions.map((prec, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      fontSize: '11.5px',
                      color: 'var(--text-main)',
                      lineHeight: 1.5,
                      background: 'rgba(255,255,255,0.01)',
                      border: '1px solid var(--border-light)',
                      padding: '10px 12px',
                      borderRadius: '6px',
                    }}
                  >
                    <span style={{ color: 'var(--color-primary)', fontWeight: 800 }}>{i + 1}.</span>
                    <span>{prec}</span>
                  </div>
                ))}
              </div>
            </div>

          </div>

        </div>
      )}

    </div>
  );
}
