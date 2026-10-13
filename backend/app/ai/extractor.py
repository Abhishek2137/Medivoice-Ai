"""Appointment data extraction using the Groq API."""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any

from dotenv import load_dotenv

load_dotenv()


def extract_appointment(user_text: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract appointment information from user text using the Groq API.
    
    Falls back to demo mode if API key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    
    # Use demo mode if no API key configured
    if not api_key or api_key == "your_groq_api_key_here":
        return _extract_appointment_demo(user_text, current_state)
    
    # Try to use the real Groq API
    try:
        from groq import Groq
    except ImportError as error:
        print(f"Warning: groq package not available, falling back to demo mode: {error}")
        return _extract_appointment_demo(user_text, current_state)
    
    try:
        from .prompts import get_extraction_prompt, format_state_for_prompt
        
        # Build the prompt with current state context
        system_prompt = get_extraction_prompt(current_state)
        
        # Prepare context message showing current state
        state_context = f"Current conversation state:\n{format_state_for_prompt(current_state)}\n\n"
        user_message = f"{state_context}New user message: {user_text}"
        
        # Call Groq's OpenAI-compatible chat API.
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        
        # Parse the response
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response
        extracted_data = parse_json_response(response_text)
        
        # Normalize date and time formats
        extracted_data = normalize_appointment_data(extracted_data)
        date_fallback = _extract_appointment_demo(user_text, current_state).get("date")
        if not extracted_data.get("date") and date_fallback:
            extracted_data["date"] = date_fallback
        
        return extracted_data
        
    except Exception as error:
        print(f"Error calling Groq API: {error}. Using demo mode.")
        return _extract_appointment_demo(user_text, current_state)


def parse_json_response(text: str) -> Dict[str, Any]:
    """
    Extract JSON from Groq response text.
    
    The model might wrap JSON in markdown code blocks or extra text.
    """
    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        json_str = text[start:end].strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Try to extract JSON from triple backticks
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        json_str = text[start:end].strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # If all else fails, return empty dict
    return {}


def normalize_appointment_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize appointment data:
    - Convert date references to YYYY-MM-DD format
    - Convert time references to HH:MM format
    """
    normalized = {}
    
    for key, value in data.items():
        if value is None or value == "":
            continue
        
        if key == "date" and isinstance(value, str):
            normalized[key] = normalize_date(value)
        elif key == "time" and isinstance(value, str):
            normalized[key] = normalize_time(value)
        elif key == "symptoms" and isinstance(value, list):
            normalized[key] = [s.strip() for s in value if s]
        else:
            normalized[key] = value
    
    return normalized


def normalize_date(date_str: str) -> str:
    """
    Convert various date formats to YYYY-MM-DD.

    Supports: "tomorrow", "next week", natural dates, and formatted dates.
    """
    date_str = date_str.lower().strip()
    today = datetime.now().date()

    if date_str == "tomorrow":
        return (today + timedelta(days=1)).isoformat()

    if date_str == "today":
        return today.isoformat()

    # Try common date formats
    for fmt in [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]:
        try:
            parsed = datetime.strptime(date_str, fmt).date()
            return parsed.isoformat()
        except ValueError:
            continue

    # If already in YYYY-MM-DD format, return as is
    if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
        return date_str

    cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", date_str, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "").strip()

    for fmt in [
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
    ]:
        try:
            parsed = datetime.strptime(cleaned, fmt).date()
            return parsed.isoformat()
        except ValueError:
            continue

    for fmt in [
        "%d %B",
        "%d %b",
        "%B %d",
        "%b %d",
    ]:
        try:
            parsed = datetime.strptime(f"{cleaned} {today.year}", f"{fmt} %Y").date()
            return parsed.isoformat()
        except ValueError:
            continue

    # Return original if can't parse (let conversation manager handle it)
    return date_str


def normalize_time(time_str: str) -> str:
    """
    Convert various time formats to HH:MM.
    
    Supports: "6 PM", "18:00", "6:30 PM", natural times like "morning", "afternoon".
    """
    time_str = time_str.lower().strip()
    
    # Handle natural time references
    if time_str in ["morning", "early morning"]:
        return "09:00"
    if time_str in ["afternoon", "midday"]:
        return "14:00"
    if time_str in ["evening", "night"]:
        return "18:00"
    
    # Try to parse AM/PM format
    for fmt in ["%I:%M %p", "%I %p", "%I:%M%p", "%I%p"]:
        try:
            parsed = datetime.strptime(time_str.replace("around ", "").strip(), fmt).time()
            return parsed.strftime("%H:%M")
        except ValueError:
            continue
    
    # Try 24-hour format
    for fmt in ["%H:%M", "%H%M"]:
        try:
            parsed = datetime.strptime(time_str, fmt).time()
            return parsed.strftime("%H:%M")
        except ValueError:
            continue
    
    # If already in HH:MM format, return as is
    if len(time_str) == 5 and time_str[2] == ":":
        return time_str
    
    # Return original if can't parse
    return time_str


def _extract_appointment_demo(user_text: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Demo extraction for testing without the Groq API.
    
    Extracts basic info from the text using simple pattern matching.
    """
    extracted = {}
    text_lower = user_text.lower()
    
    # Simple name extraction (words after "my name is" or "i'm" or "i am")
    if "my name is" in text_lower:
        parts = text_lower.split("my name is")
        if len(parts) > 1:
            name = parts[1].split()[0].strip(".,!?").capitalize()
            if name and name not in ["a", "the", "and"]:
                extracted["patient_name"] = name
    elif "i'm " in text_lower or "im " in text_lower:
        pattern = r"i[' ]m\s+(\w+)"
        import re
        match = re.search(pattern, text_lower)
        if match:
            name = match.group(1).strip(".,!?").capitalize()
            extracted["patient_name"] = name

    # Specific doctor extraction for requests such as "book Dr Sharma".
    import re
    doctor_match = re.search(
        r"(?:doctor|dr\.?)\s+([a-z]+(?:\s+[a-z]+){0,2})",
        text_lower,
    )
    if doctor_match:
        extracted["doctor_name"] = " ".join(
            part.capitalize() for part in doctor_match.group(1).split()
        )
    
    # Doctor type extraction
    doctor_types = {
        "cardiologist": "Cardiology",
        "dermatologist": "Dermatology", 
        "dentist": "Dentistry",
        "orthopedic": "Orthopedics",
        "skin doctor": "Dermatology",
        "heart doctor": "Cardiology",
        "bone doctor": "Orthopedics",
        "eye doctor": "Ophthalmology",
        "neurologist": "Neurology",
        "pediatrician": "Pediatrics",
    }
    
    for key, value in doctor_types.items():
        if key in text_lower:
            extracted["specialization"] = value
            break
    
    # Date extraction
    if "tomorrow" in text_lower:
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        extracted["date"] = tomorrow
    elif "today" in text_lower:
        extracted["date"] = datetime.now().date().isoformat()
    else:
        month_pattern = (
            r"(january|jan|february|feb|march|mar|april|apr|may|"
            r"june|jun|july|jul|august|aug|september|sept|sep|"
            r"october|oct|november|nov|december|dec)"
        )
        day_first_match = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
            + month_pattern
            + r"(?:,?\s+(\d{4}))?\b",
            text_lower,
        )
        if day_first_match:
            day, month_name, year = day_first_match.groups()
            month_name = "sep" if month_name == "sept" else month_name
            date_text = f"{day} {month_name} {year or datetime.now().year}"
        else:
            date_match = re.search(
                r"\b"
                + month_pattern
                + r"\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b",
                text_lower,
            )
            if date_match:
                month_name, day, year = date_match.groups()
                month_name = "sep" if month_name == "sept" else month_name
                date_text = f"{month_name} {day} {year or datetime.now().year}"

        if day_first_match or date_match:
            normalized_date = normalize_date(date_text)
            try:
                datetime.strptime(normalized_date, "%Y-%m-%d")
            except ValueError:
                pass
            else:
                extracted["date"] = normalized_date
    
    # Time extraction, including speech variants such as "9 p.m.".
    # Also support bare or ranged numeric times such as "9-10" or "9 to 10".
    range_match = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(?:-|to)\s*(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b",
        text_lower,
    )
    if range_match:
        hour = int(range_match.group(1))
        minute = int(range_match.group(2) or "0")
        meridiem = (range_match.group(5) or "").replace(".", "")
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        extracted["time"] = f"{hour:02d}:{minute:02d}"
    else:
        time_match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b",
            text_lower,
        )
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or "0")
            meridiem = time_match.group(3).replace(".", "")
            if meridiem == "pm" and hour != 12:
                hour += 12
            if meridiem == "am" and hour == 12:
                hour = 0
            extracted["time"] = f"{hour:02d}:{minute:02d}"
        else:
            bare_time_match = re.search(
                r"\b(?:at|around|for|time\s+is)\s*(\d{1,2})(?::(\d{2}))?\b",
                text_lower,
            )
            if (
                bare_time_match is None
                and current_state.get("date")
                and not extracted.get("date")
            ):
                bare_time_match = re.fullmatch(
                    r"\s*(\d{1,2})(?::(\d{2}))?\s*", text_lower
                )
            if bare_time_match:
                hour = int(bare_time_match.group(1))
                minute = int(bare_time_match.group(2) or "0")
                extracted["time"] = f"{hour:02d}:{minute:02d}"
            else:
                time_keywords = {
                    "morning": "09:00",
                    "afternoon": "14:00",
                    "evening": "18:00",
                }
                for key, value in time_keywords.items():
                    if key in text_lower:
                        extracted["time"] = value
                        break
    
    # Symptoms extraction
    symptom_keywords = ["headache", "fever", "cough", "cold", "pain", "ache", "itching", "rash", "allergy"]
    found_symptoms = []
    for symptom in symptom_keywords:
        if symptom in text_lower:
            found_symptoms.append(symptom)
    
    if found_symptoms:
        extracted["symptoms"] = found_symptoms
    
    return extracted
