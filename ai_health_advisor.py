"""
ai_health_advisor.py - AI Clinical Insights & Interactive Patient Q&A for MediTrust Health Manager
Powered by Google Gemini 2.5 Flash
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def _get_genai_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not GENAI_AVAILABLE:
        return None
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=25000),
    )


def format_category_name(category):
    names = {
        "blood_pressure": "Blood Pressure",
        "blood_sugar": "Blood Sugar / Glycemic Control",
        "heart_rate": "Heart Rate / Pulse",
        "weight": "Body Weight & Composition",
        "sleep": "Sleep Duration & Efficiency",
        "sleep_duration": "Sleep Duration & Efficiency",
        "temperature": "Body Temperature",
    }
    return names.get(category, category.replace("_", " ").title())


def _rule_based_fallback_insight(category, latest, history):
    """
    Intelligent clinical fallback when Gemini API key is missing or offline.
    Provides 5-7 informative sentences based on medical guidelines.
    """
    cat = category.lower()
    hist_count = len(history) if history else 0

    if "pressure" in cat:
        sys_val = latest.get("value")
        dia_val = latest.get("secondary_value")
        status = "normal"
        if sys_val >= 140 or dia_val >= 90:
            status = "Stage 2 Hypertension"
        elif sys_val >= 130 or dia_val >= 80:
            status = "Stage 1 Hypertension"
        elif sys_val >= 120 and dia_val < 80:
            status = "Elevated"
        else:
            status = "Optimal / Normal"

        return (
            f"Your latest blood pressure reading of {sys_val}/{dia_val} mmHg falls within the {status} range based on standard American Heart Association guidelines. "
            f"Looking across your {hist_count} previously recorded session(s), this reading provides key insight into your ongoing cardiovascular baseline. "
            f"Readings in this tier reflect the resistance within your arterial walls as your heart pumps and rests between contractions. "
            f"Common everyday contributors to temporary shifts include dietary sodium intake, stress, caffeine consumption, hydration levels, and recent physical exertion. "
            f"Maintaining consistent sleep, balanced nutrition with potassium-rich whole foods, and gentle cardiovascular activity can positively support arterial flexibility. "
            f"If your readings consistently stay elevated or if you experience dizziness, headache, or chest discomfort, please consult your physician for clinical management. "
            f"Please remember that MediTrust AI insights are educational records and do not substitute for formal medical evaluation."
        )

    elif "sugar" in cat:
        val = latest.get("value")
        unit = latest.get("unit", "mg/dL")
        m_type = latest.get("measurement_type", "blood_sugar")
        return (
            f"Your latest recorded blood sugar value is {val} {unit} ({m_type.replace('_', ' ').title()}). "
            f"Evaluating this against your previous {hist_count} glycemic log(s) helps identify insulin response patterns throughout your day. "
            f"Post-meal and fasting glucose fluctuations directly reflect how carbohydrates are metabolized and cleared from your bloodstream. "
            f"Variations can frequently be influenced by meal composition, glycemic index, physical movement after meals, hydration, and sleep regularity. "
            f"To foster steady glucose levels, prioritize lean proteins, high-fiber vegetables, and structured meal timings while minimizing refined sugars. "
            f"Contact your healthcare provider if you observe sudden unexplained spikes or drops outside your physician's personalized target ranges. "
            f"This analysis is provided for health tracking purposes and is not a medical diagnosis."
        )

    elif "heart" in cat:
        val = latest.get("value")
        status = "optimal resting range (60-100 BPM)" if 60 <= val <= 100 else ("elevated (tachycardia range)" if val > 100 else "low (bradycardia range)")
        return (
            f"Your recorded heart rate is {val} BPM, which is in the {status} for resting adults. "
            f"Compared with your past {hist_count} recorded heart rate measurement(s), this reflects your autonomic nervous system balance and cardiovascular readiness. "
            f"Pulse rate fluctuations indicate how hard the heart is working to circulate oxygenated blood to vital organs and peripheral tissues. "
            f"Transient changes in pulse are routinely triggered by emotional stress, caffeine, ambient temperature, hydration state, or recent movement. "
            f"Practicing rhythmic diaphragmatic breathing, staying properly hydrated, and regular cardiovascular conditioning help sustain optimal cardiac recovery. "
            f"Seek immediate medical attention if an abnormal heart rate is accompanied by chest pain, shortness of breath, or lightheadedness. "
            f"Note that MediTrust health records are strictly informational."
        )

    elif "weight" in cat:
        val = latest.get("value")
        unit = latest.get("unit", "kg")
        return (
            f"Your current weight entry is recorded at {val} {unit}. "
            f"Tracking this entry across your {hist_count} previous log(s) highlights your gradual body composition and metabolic trends over time. "
            f"Day-to-day weight fluctuations of 1 to 2 kg are biologically normal and primarily reflect water retention, sodium intake, and glycogen storage rather than fat loss or gain. "
            f"Long-term stability or deliberate directional progress depends on steady dietary habits, physical activity, and metabolic rate. "
            f"Focus on sustained hydration, nutrient-dense whole foods, and resistance training to preserve lean muscle mass. "
            f"Consult a registered dietitian or your physician for personalized dietary plans aligned with your medical profile. "
            f"This summary is an educational record and not medical advice."
        )

    elif "sleep" in cat:
        duration = latest.get("value")
        efficiency = latest.get("secondary_value")
        return (
            f"You logged {duration} hours of sleep with a calculated sleep efficiency of {efficiency}%. "
            f"Reviewing this alongside your {hist_count} previous sleep session(s) offers valuable visibility into your circadian rhythm stability. "
            f"Adequate slow-wave and REM sleep cycles are essential for immune function, cognitive restoration, hormonal equilibrium, and cardiovascular recovery. "
            f"Disruptions in sleep quality frequently stem from blue light exposure before bedtime, late meals, caffeine, or inconsistent sleep-wake schedules. "
            f"Establishing a dark, cool sleeping environment and winding down with screen-free relaxation can substantially enhance sleep architecture. "
            f"Persistent insomnia or unrefreshing sleep should be evaluated with your healthcare provider to check for underlying sleep disorders. "
            f"MediTrust sleep records provide informational wellness tracking."
        )

    elif "temp" in cat:
        val = latest.get("value")
        status = "within normal physiological range (36.5°C - 37.5°C)" if 36.5 <= val <= 37.5 else ("fever / elevated range" if val > 37.5 else "hypothermic / low range")
        return (
            f"Your body temperature is logged at {val} °C, which is {status}. "
            f"Analyzing this reading in context with your {hist_count} prior record(s) helps track your thermoregulatory balance. "
            f"Body temperature shifts can indicate active immune responses, inflammatory defense, hormonal fluctuations, or ambient environmental effects. "
            f"Fever patterns often accompany viral or bacterial immune activation and may be accompanied by sweating, chills, or fatigue. "
            f"Rest, adequate fluid intake with electrolytes, and comfortable loose clothing help support your body's natural thermal regulation. "
            f"Promptly consult a doctor if a high fever persists, does not respond to routine care, or is paired with severe symptoms. "
            f"This analysis is strictly informational and does not constitute medical treatment advice."
        )

    return (
        f"Your latest reading of {latest.get('value')} {latest.get('unit', '')} has been logged in your health profile. "
        f"Tracking this measurement over time against your {hist_count} historical reading(s) helps identify personal wellness trajectories. "
        f"Maintaining steady baseline values supports vital metabolic and physiological balance. "
        f"Lifestyle elements such as hydration, stress management, quality sleep, and nutrition play a central role in your readings. "
        f"Consistent logging allows you and your physician to spot patterns early and adjust care plans effectively. "
        f"Discuss any unexpected changes or symptoms directly with your licensed healthcare provider. "
        f"MediTrust observations are informational only."
    )


def generate_measurement_insight(category, latest_reading, history_readings):
    """
    Generates a 5 to 7 sentence clinical observation on trend, significance,
    physiological effects, severity, and lifestyle tips using Gemini 2.5 Flash.
    Falls back gracefully if offline.
    """
    if not latest_reading:
        return "No measurement data available yet to generate clinical insights. Log your first reading above!"

    client = _get_genai_client()
    if not client:
        return _rule_based_fallback_insight(category, latest_reading, history_readings)

    category_name = format_category_name(category)

    # Format history as concise text for prompt
    hist_summary = []
    for r in (history_readings or [])[:10]:
        val = r.get("value")
        sec = r.get("secondary_value")
        unit = r.get("unit", "")
        val_str = f"{val}/{sec} {unit}" if sec is not None else f"{val} {unit}"
        rec = r.get("recorded_at", "Past")
        notes = f" (Notes: {r.get('context')})" if r.get("context") else ""
        hist_summary.append(f"- {rec}: {val_str}{notes}")

    hist_text = "\n".join(hist_summary) if hist_summary else "No earlier readings logged yet."

    cur_val = latest_reading.get("value")
    cur_sec = latest_reading.get("secondary_value")
    cur_unit = latest_reading.get("unit", "")
    cur_str = f"{cur_val}/{cur_sec} {cur_unit}" if cur_sec is not None else f"{cur_val} {cur_unit}"
    cur_date = latest_reading.get("recorded_at", "Current")
    cur_notes = latest_reading.get("context") or "None"

    prompt = f"""
You are an expert clinical health intelligence assistant for the MediTrust patient portal.
Analyze the patient's latest {category_name} measurement in the context of their historical readings.

Patient Measurement Details:
- Category: {category_name}
- Latest Reading: {cur_str} recorded at {cur_date}
- Context/Notes: {cur_notes}

Previous Historical Readings (chronological order):
{hist_text}

Task:
Produce a thoughtful, highly informative clinical insight of EXACTLY 5 to 7 sentences covering:
1. Chronological Trend: Compare this latest reading to their historical baseline or recent average (rising, falling, fluctuating, or well-controlled).
2. Clinical Significance & Severity: Classify the reading according to established medical reference standards (e.g. AHA, ADA, WHO).
3. Physiological Implications: Explain what this measurement means for internal organ workload, vascular/metabolic strain, or systemic recovery.
4. Contributing Triggers: Mention everyday factors that may have influenced this reading (e.g., diet, hydration, physical exertion, stress, timing, sleep).
5. Actionable Lifestyle Suggestions: Offer 1-2 practical, safe wellness or dietary habits that can support healthy balance.
6. Clinical Precaution: Mention red flag indicators or when the patient should alert their physician.
7. Disclaimer: Reiterate that this observation is informational and not a substitute for formal diagnosis.

Constraints:
- Strictly between 5 and 7 sentences in total.
- Empathetic, encouraging, and clinically rigorous tone.
- Do NOT prescribe medications or make definitive diagnostic pronouncements.
- Output clean text without bullet points or markdown headings.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            ),
        )
        insight = response.text.strip()
        return insight if insight else _rule_based_fallback_insight(category, latest_reading, history_readings)
    except Exception:
        return _rule_based_fallback_insight(category, latest_reading, history_readings)
    finally:
        client.close()


def answer_followup_question(category, latest_reading, history_readings, previous_insight, question):
    """
    Answers a patient's interactive follow-up question regarding their health insight or reading.
    Returns a concise, empathetic, informative 3-5 sentence answer.
    """
    if not question or not question.strip():
        return "Please ask a question regarding your measurement or health trend."

    client = _get_genai_client()
    category_name = format_category_name(category)

    cur_val = latest_reading.get("value") if latest_reading else "N/A"
    cur_sec = latest_reading.get("secondary_value") if latest_reading else None
    cur_unit = latest_reading.get("unit", "") if latest_reading else ""
    cur_str = f"{cur_val}/{cur_sec} {cur_unit}" if cur_sec is not None else f"{cur_val} {cur_unit}"

    if not client:
        return (
            f"Regarding your question about {category_name} (latest reading: {cur_str}): "
            f"Daily fluctuations are influenced by lifestyle factors like hydration, nutrition, restorative sleep, and stress levels. "
            f"Adopting balanced daily routines such as moderate movement and reduced processed foods generally supports positive trends. "
            f"Always consult your primary care doctor for specific personal treatment plans or if you notice recurring abnormal symptoms."
        )

    prompt = f"""
You are an empathetic, clinical health assistant for MediTrust.
A patient has a follow-up question regarding their {category_name} tracking and recent AI insight.

Context:
- Category: {category_name}
- Latest Reading: {cur_str}
- Previous AI Clinical Insight:
"{previous_insight}"

Patient's Question:
"{question}"

Task:
Respond in 3 to 5 clear, compassionate, and informative sentences that:
1. Directly and helpfully answer the patient's specific question (e.g. food advice, exercise timing, physiology, normal variations).
2. Ground the answer in general medical evidence.
3. Suggest practical questions or observations the patient can bring to their next doctor visit.
4. Maintain medical safety: Do NOT prescribe medications, adjust drug dosages, or diagnose conditions.

Output plain text only.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            ),
        )
        ans = response.text.strip()
        return ans if ans else "Thank you for asking. Maintaining balanced lifestyle habits supports optimal health. Please discuss any persistent questions with your healthcare provider."
    except Exception:
        return (
            f"Regarding your question about {category_name} (latest reading: {cur_str}): "
            f"Daily fluctuations are influenced by lifestyle factors like hydration, nutrition, restorative sleep, and stress levels. "
            f"Adopting balanced daily routines such as moderate movement and reduced processed foods generally supports positive trends. "
            f"Always consult your primary care doctor for specific personal treatment plans or if you notice recurring abnormal symptoms."
        )
    finally:
        client.close()
