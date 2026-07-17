/**
 * frontend/src/components/CitizenAdvisoryPanel.jsx
 *
 * Citizen Health Risk Advisory Panel (English & Hindi).
 * Displays AQI severity category, health warnings, and recommended precautions.
 * Supports dual languages and features a client-side offline fallback
 * if the backend API is unreachable.
 */

import { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Languages,
  CheckCircle2,
  AlertTriangle,
  Info,
  Sparkles,
} from 'lucide-react';

// ─── Local CPCB Fallback Database ──────────────────────────────────────────────

const LOCAL_AQI_BANDS = [
  {
    min: 0,
    max: 50,
    category_en: "Good",
    category_hi: "अच्छा",
    message_en: "Air quality is satisfactory, and air pollution poses little or no risk.",
    message_hi: "वायु की गुणवत्ता संतोषजनक है, और वायु प्रदूषण से कोई या बहुत कम जोखिम है।",
    precautions_en: [
      "No precautions needed. Great day for outdoor activities.",
      "Keep windows open to maintain ventilation."
    ],
    precautions_hi: [
      "किसी सावधानी की आवश्यकता नहीं है। बाहरी गतिविधियों के लिए बहुत अच्छा दिन है।",
      "कमरों में वेंटिलेशन बनाए रखने के लिए खिड़कियाँ खुली रखें।"
    ]
  },
  {
    min: 51,
    max: 100,
    category_en: "Satisfactory",
    category_hi: "संतोषजनक",
    message_en: "Air quality is acceptable; however, there may be a moderate concern for sensitive individuals.",
    message_hi: "वायु की गुणवत्ता स्वीकार्य है; हालांकि, संवेदनशील लोगों के लिए हल्की चिंता हो सकती है।",
    precautions_en: [
      "Sensitive people (e.g. with asthma) should consider reducing heavy outdoor exertion.",
      "Monitor air quality changes if you suffer from respiratory issues."
    ],
    precautions_hi: [
      "संवेदनशील लोगों (जैसे अस्थमा से पीड़ित) को भारी बाहरी परिश्रम कम करने पर विचार करना चाहिए।",
      "यदि आप सांस की बीमारी से पीड़ित हैं, तो वायु गुणवत्ता में बदलावों पर नजर रखें।"
    ]
  },
  {
    min: 101,
    max: 200,
    category_en: "Moderate",
    category_hi: "सामान्य रूप से प्रदूषित",
    message_en: "Members of sensitive groups may experience health effects. The general public is less likely to be affected.",
    message_hi: "संवेदनशील समूहों के लोगों को स्वास्थ्य प्रभाव महसूस हो सकते हैं। आम लोगों के प्रभावित होने की संभावना कम है।",
    precautions_en: [
      "Sensitive groups should limit prolonged outdoor activities.",
      "Take more breaks during outdoor activities if symptoms arise."
    ],
    precautions_hi: [
      "संवेदनशील समूहों को लंबे समय तक बाहरी गतिविधियों को सीमित करना चाहिए।",
      "लक्षण उत्पन्न होने पर बाहरी गतिविधियों के दौरान अधिक विश्राम लें।"
    ]
  },
  {
    min: 201,
    max: 300,
    category_en: "Poor",
    category_hi: "खराब",
    message_en: "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
    message_hi: "हर किसी को स्वास्थ्य प्रभाव महसूस होना शुरू हो सकता है; संवेदनशील समूहों को अधिक गंभीर प्रभाव हो सकते हैं।",
    precautions_en: [
      "Wear protective masks (N95 or equivalent) when outdoors.",
      "Avoid strenuous outdoor activities, especially children and seniors.",
      "Close windows to avoid outdoor dust and smog."
    ],
    precautions_hi: [
      "बाहर जाते समय सुरक्षात्मक मास्क (N95 या समकक्ष) पहनें।",
      "भारी बाहरी गतिविधियों से बचें, विशेष रूप से बच्चे और बुजुर्ग व्यक्ति।",
      "बाहरी धूल और धुंध से बचने के लिए खिड़कियाँ बंद रखें।"
    ]
  },
  {
    min: 301,
    max: 400,
    category_en: "Very Poor",
    category_hi: "बहुत खराब",
    message_en: "Health alert: everyone may experience more serious health effects. Immediate exposure reduction is advised.",
    message_hi: "स्वास्थ्य चेतावनी: सभी को गंभीर स्वास्थ्य प्रभाव महसूस हो सकते हैं। बाहरी संपर्क तुरंत कम करने की सलाह दी जाती है।",
    precautions_en: [
      "Sensitive groups should remain indoors. General population should avoid outdoor activities.",
      "Wear N95 masks if outdoor travel is mandatory.",
      "Use air purifiers indoors and close all windows.",
      "Avoid burning any dry leaves or waste nearby."
    ],
    precautions_hi: [
      "संवेदनशील समूह घर के अंदर ही रहें। आम लोगों को बाहरी गतिविधियों से बचना चाहिए।",
      "बाहरी यात्रा अनिवार्य होने पर N95 मास्क पहनें।",
      "कमरे में एयर प्यूरीफायर चलाएं और खिड़कियाँ बंद रखें।",
      "आसपास सूखे पत्ते या कचरा जलाने से बचें।"
    ]
  },
  {
    min: 401,
    max: 9999,
    category_en: "Severe",
    category_hi: "गंभीर",
    message_en: "Emergency conditions. Health warnings of emergency levels. General population is severely affected.",
    message_hi: "आपातकालीन स्थिति। स्वास्थ्य पर गंभीर प्रभाव। आम आबादी गंभीर रूप से प्रभावित होती है।",
    precautions_en: [
      "Avoid all outdoor exertion and physical activities.",
      "General public must remain indoors. Sensitive individuals must stay in clean air rooms.",
      "Keep all windows and doors tightly shut; run indoor air purifiers continuously.",
      "Wear well-fitted N95/N99 masks if stepping out is absolutely unavoidable."
    ],
    precautions_hi: [
      "सभी प्रकार के बाहरी शारीरिक परिश्रम और गतिविधियों से बचें।",
      "आम जनता घर के अंदर ही रहे। संवेदनशील लोग साफ हवा वाले कमरों में रहें।",
      "सभी खिड़कियाँ और दरवाजे कसकर बंद रखें; कमरे में लगातार एयर प्यूरीफायर चलाएं।",
      "यदि बाहर जाना बिल्कुल अपरिहार्य हो तो फिटेड N95/N99 मास्क पहनें।"
    ]
  }
];

const LOCAL_SOURCE_PRECAUTIONS = {
  agricultural_burning: {
    en: "Avoid areas downwind of agricultural fields/stubble burning to prevent acute smoke inhalation.",
    hi: "तीव्र धुएँ के सांस में जाने से बचने के लिए फसल अवशेष जलाने वाली जगहों से अनुकूल हवा की दिशा में जाने से बचें।"
  },
  traffic: {
    en: "Avoid walking or exercising near high-traffic corridors during peak commute hours.",
    hi: "भीड़भाड़ वाले समय में व्यस्त सड़कों या मुख्य मार्गों के पास टहलने या व्यायाम करने से बचें।"
  },
  industrial: {
    en: "Ensure indoor ventilation systems have high-efficiency particulate air (HEPA) filters if near industrial zones.",
    hi: "औद्योगिक क्षेत्रों के पास होने पर इनडोर वेंटिलेशन सिस्टम में उच्च दक्षता वाले कण हवा (HEPA) फिल्टर लगाना सुनिश्चित करें।"
  }
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getAqiStyle(aqi) {
  if (aqi <= 50)  return { label_en: 'Good',          label_hi: 'अच्छा',              color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' };
  if (aqi <= 100) return { label_en: 'Satisfactory',  label_hi: 'संतोषजनक',           color: '#84cc16', bg: 'rgba(132, 204, 22, 0.15)' };
  if (aqi <= 200) return { label_en: 'Moderate',      label_hi: 'सामान्य रूप से प्रदूषित', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' };
  if (aqi <= 300) return { label_en: 'Poor',          label_hi: 'खराब',               color: '#f97316', bg: 'rgba(249, 115, 22, 0.15)' };
  if (aqi <= 400) return { label_en: 'Very Poor',     label_hi: 'बहुत खराब',           color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' };
  return { label_en: 'Severe', label_hi: 'गंभीर', color: '#dc2626', bg: 'rgba(220, 38, 38, 0.2)' };
}

export default function CitizenAdvisoryPanel({ currentAqi, primaryCause, forecastAqi, apiBase }) {
  const [language, setLanguage] = useState('en'); // 'en' | 'hi'
  const [advisory, setAdvisory] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [isLlm, setIsLlm]       = useState(false);
  const [enableLlm, setEnableLlm] = useState(false); // default to false for instant local mode

  const baselineAqi = Math.round(currentAqi || 300);
  const forecastVal = forecastAqi ? Math.round(forecastAqi) : null;
  const source      = primaryCause || 'traffic';
  const aqiStyle    = getAqiStyle(baselineAqi);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    async function fetchAdvisory() {
      try {
        const url =
          `${apiBase}/api/v1/advisory` +
          `?current_aqi=${baselineAqi}` +
          (forecastVal ? `&forecasted_aqi=${forecastVal}` : '') +
          `&primary_cause=${source}` +
          `&language=${language}` +
          `&enable_llm=${enableLlm}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
        const data = await res.json();

        if (isMounted) {
          setAdvisory({
            category: data.aqi_category,
            message: data.health_message,
            precautions: data.recommended_precautions,
            llm_error: data.llm_error,
          });
          setIsLlm(!data.llm_error);
          setLoading(false);
        }
      } catch (err) {
        console.warn("Advisory API failed, running local fallback: ", err);
        // Local fallback generation
        if (isMounted) {
          let band = LOCAL_AQI_BANDS[LOCAL_AQI_BANDS.length - 1];
          for (let b of LOCAL_AQI_BANDS) {
            if (baselineAqi >= b.min && baselineAqi <= b.max) {
              band = b;
              break;
            }
          }

          let category = language === 'hi' ? band.category_hi : band.category_en;
          let message = language === 'hi' ? band.message_hi : band.message_en;
          let precautions = language === 'hi' ? [...band.precautions_hi] : [...band.precautions_en];

          if (LOCAL_SOURCE_PRECAUTIONS[source]) {
            precautions.push(
              language === 'hi' ? LOCAL_SOURCE_PRECAUTIONS[source].hi : LOCAL_SOURCE_PRECAUTIONS[source].en
            );
          }

          setAdvisory({
            category,
            message,
            precautions,
            llm_error: true,
          });
          setIsLlm(false);
          setLoading(false);
        }
      }
    }

    fetchAdvisory();

    return () => {
      isMounted = false;
    };
  }, [baselineAqi, forecastVal, source, language, enableLlm, apiBase]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '24px' }}>
      
      {/* Left Card: Status Summary */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={18} color="var(--color-primary)" />
          <div>
            <h2 style={{ fontSize: '15px', fontWeight: 700 }}>Citizen Advisory</h2>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Localized health warnings and protective guide</p>
          </div>
        </div>

        {/* Big Status Badge */}
        <div
          className="glass-panel"
          style={{
            background: aqiStyle.bg,
            border: `1px solid ${aqiStyle.color}`,
            borderRadius: '12px',
            padding: '24px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '8px',
            boxShadow: `0 0 20px ${aqiStyle.color}15`,
          }}
        >
          <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '1px' }}>
            SEVERITY STATUS
          </span>
          <span style={{ fontSize: '24px', fontWeight: 800, color: aqiStyle.color }}>
            {language === 'hi' ? aqiStyle.label_hi : aqiStyle.label_en.toUpperCase()}
          </span>
          <div style={{ fontSize: '36px', fontWeight: 900, color: '#fff', margin: '4px 0' }}>
            AQI {baselineAqi}
          </div>
          {forecastVal && (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span>24h Forecast:</span>
              <span style={{ color: getAqiStyle(forecastVal).color, fontWeight: 700 }}>{forecastVal}</span>
            </div>
          )}
        </div>

        {/* Details Card */}
        <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Primary Source:</span>
            <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
              {source.replace('_', ' ').toUpperCase()}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Advisory Engine:</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: isLlm ? 'var(--color-success)' : 'var(--color-primary)' }}>
              {isLlm ? <Sparkles size={11} /> : <Info size={11} />}
              <strong>{isLlm ? "GEN-AI SUMMARY" : "LOCAL RULE-BASED"}</strong>
            </span>
          </div>
        </div>

        {/* Language selector toggle */}
        <div className="glass-panel" style={{ padding: '6px', display: 'flex', gap: '6px', borderRadius: '8px' }}>
          <button
            onClick={() => setLanguage('en')}
            style={{
              flex: 1,
              padding: '6px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: language === 'en' ? 700 : 500,
              background: language === 'en' ? 'rgba(0, 240, 255, 0.12)' : 'transparent',
              color: language === 'en' ? '#fff' : 'var(--text-muted)',
              transition: 'all 0.2s',
            }}
          >
            ENGLISH
          </button>
          <button
            onClick={() => setLanguage('hi')}
            style={{
              flex: 1,
              padding: '6px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: language === 'hi' ? 700 : 500,
              background: language === 'hi' ? 'rgba(0, 240, 255, 0.12)' : 'transparent',
              color: language === 'hi' ? '#fff' : 'var(--text-muted)',
              transition: 'all 0.2s',
            }}
          >
            हिंदी / HINDI
          </button>
        </div>

        {/* AI Generator Toggle */}
        <div className="glass-panel" style={{ padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderRadius: '8px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Sparkles size={12} color={enableLlm ? 'var(--color-success)' : 'var(--text-dark)'} />
            <span style={{ fontWeight: 600 }}>AI ADVISORY (LLM)</span>
          </span>
          <button
            onClick={() => setEnableLlm(!enableLlm)}
            style={{
              background: enableLlm ? 'var(--color-success)' : 'rgba(255,255,255,0.06)',
              border: 'none',
              borderRadius: '20px',
              width: '36px',
              height: '18px',
              position: 'relative',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: '#fff',
                position: 'absolute',
                left: enableLlm ? '20px' : '4px',
                transition: 'left 0.2s',
              }}
            />
          </button>
        </div>
      </div>

      {/* Right Column: Advisory Details */}
      <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px', justifyContent: 'center' }}>
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
            {/* Loading skeletons */}
            <div style={{ height: '20px', width: '40%', background: 'var(--border-light)', borderRadius: '4px', className: 'pulse-glow' }}></div>
            <div style={{ height: '60px', width: '100%', background: 'var(--border-light)', borderRadius: '6px', className: 'pulse-glow' }}></div>
            <div style={{ height: '20px', width: '30%', background: 'var(--border-light)', borderRadius: '4px', className: 'pulse-glow', marginTop: '10px' }}></div>
            <div style={{ height: '30px', width: '100%', background: 'var(--border-light)', borderRadius: '6px', className: 'pulse-glow' }}></div>
            <div style={{ height: '30px', width: '100%', background: 'var(--border-light)', borderRadius: '6px', className: 'pulse-glow' }}></div>
          </div>
        ) : (
          <>
            {/* Warning Message Card */}
            <div
              style={{
                borderLeft: `4px solid ${aqiStyle.color}`,
                background: 'rgba(255, 255, 255, 0.01)',
                padding: '16px',
                borderRadius: '0 8px 8px 0',
              }}
            >
              <h3 style={{ fontSize: '13px', fontWeight: 700, color: '#fff', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertTriangle size={14} color={aqiStyle.color} />
                {language === 'hi' ? "स्वास्थ्य चेतावनी" : "HEALTH WARNING"}
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-main)', lineHeight: '1.6' }}>
                {advisory?.message}
              </p>
            </div>

            {/* Precautions list */}
            <div>
              <h3 style={{ fontSize: '13px', fontWeight: 700, color: '#fff', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Languages size={14} color="var(--color-primary)" />
                {language === 'hi' ? "अनुशंसित सावधानियां" : "RECOMMENDED PRECAUTIONS"}
              </h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {advisory?.precautions.map((precaution, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-light)',
                      borderRadius: '8px',
                      padding: '12px',
                      fontSize: '11.5px',
                      color: 'var(--text-main)',
                      lineHeight: '1.4',
                    }}
                  >
                    <CheckCircle2 size={14} color="var(--color-primary)" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <span>{precaution}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Disclaimer disclaimer */}
            <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: '12px', fontSize: '9.5px', color: 'var(--text-dark)', lineHeight: '1.4' }}>
              <span style={{ fontWeight: 600 }}>{language === 'hi' ? "घोषणा:" : "DISCLAIMER:"} </span>
              {language === 'hi'
                ? "यह एक सांकेतिक स्वास्थ्य सलाह है, जो मानक CPCB गंभीरता श्रेणियों के अनुसार तैयार की गई है। यह एक नैदानिक चिकित्सा प्रोटोकॉल नहीं है।"
                : "This is an indicative health advisory, calibrated with standard CPCB severity bands. Not a clinical medical protocol."}
            </div>
          </>
        )}
      </div>

    </div>
  );
}
