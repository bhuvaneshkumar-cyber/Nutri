import os
import json
import re
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "") 
client = genai.Client(api_key=API_KEY) if API_KEY else None
MODEL_ID = "gemini-2.5-flash" 

def analyze_food_image(image_bytes):
    if not client:
        return {"error": True, "message": "API Key is missing. Please set GEMINI_API_KEY in your terminal."}
        
    prompt = """
    Analyze this food image. Provide the nutritional breakdown.
    Respond ONLY with a JSON object containing the following keys:
    "name": string (Name of the food)
    "calories": integer (Total estimated calories)
    "protein": integer (Grams of protein)
    "carbs": integer (Grams of carbohydrates)
    "fats": integer (Grams of fats)
    "advice": string (One short sentence of healthy advice regarding this food)
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                    ]
                )
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
        )
        
        # BULLETPROOF FIX: Use regex to hunt down the exact JSON block just in case the AI hallucinates conversational text around it
        raw_text = response.text.strip()
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            raw_text = match.group(0)
            
        return json.loads(raw_text)
        
    except json.JSONDecodeError:
        return {"error": True, "message": "Failed to parse AI output. Please try a clearer image."}
    except Exception as e:
        return {"error": True, "message": f"Vision API Error: {str(e)}"}

def chat_with_ai(user_message, context_data):
    if not client:
        return "System Offline: GEMINI_API_KEY environment variable is missing."
        
    sys_prompt = f"""
    You are NUtri-INO, a friendly, uplifting AI health coach. 
    Current User Stats & Context: {context_data}. 
    Keep answers concise, helpful, and under 3 sentences. 
    Use a positive, motivating tone. Include local insights if applicable.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            config=types.GenerateContentConfig(system_instruction=sys_prompt),
            contents=[user_message]
        )
        return response.text
    except Exception as e:
        return f"API Connection Failed: {str(e)}"

def generate_recipe(food_name, location, goal):
    if not client:
        return "System Offline: API key missing."
    prompt = f"""
    Act as a localized nutritionist and chef. 
    Provide a quick, simple, healthy home-cooked recipe or preparation method for '{food_name}'.
    The user is located in '{location}' and their primary health goal is '{goal}'.
    Adapt the ingredients to what is fresh, cultural, and locally available there, while strictly supporting the health goal.
    Format the response cleanly in Markdown with bold headers and bullet points. Keep it under 150 words.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.6) 
        )
        return response.text
    except Exception as e:
        return f"Could not generate recipe: {str(e)}"

def analyze_pantry_image(image_bytes, location, goal, mime_type="image/jpeg"):
    if not client:
        return "System Offline: API key missing."
    
    prompt = f"""
    You are the "Pantry Alchemist". Look at the ingredients visible in this image (fridge, pantry, or counter).
    The user lives in '{location}' and their health goal is '{goal}'.
    Invent 2 unique, simple, and delicious recipes they can make right now using ONLY the ingredients you see (plus basic pantry staples like salt, pepper, oil, water).
    If you cannot clearly see any food items, politely explain what you see instead.
    Format cleanly in Markdown. For each recipe include:
    - A catchy, localized title
    - Estimated Calories
    - Brief instructions
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                    ]
                )
            ],
            config=types.GenerateContentConfig(temperature=0.7) 
        )
        
        if response.text:
            return response.text
        else:
            return "The AI returned an empty response. The image might be too blurry or triggered a safety filter. Try a clearer photo!"
            
    except Exception as e:
        return f"Failed to analyze pantry: {str(e)}"
# --- NEW: REHAB & RECOVERY ENGINE ---
def generate_recovery_protocol(strain_description, location):
    if not client:
        return "System Offline: API key missing."
        
    prompt = f"""
    Act as an elite sports medicine dietitian and physiotherapist. 
    The user is experiencing the following strain/injury: '{strain_description}'.
    They are located in '{location}'.
    
    Provide a highly actionable recovery protocol formatted cleanly in Markdown. Include:
    1. **Immediate Mobility/Rehab Advice:** 2 specific, safe stretches or actions to take.
    2. **Anti-Inflammatory Diet Shift:** Explain briefly what macros/micronutrients they need right now to repair this specific tissue.
    3. **Healing Recipe:** 1 specific, hyper-localized recipe using ingredients available in their region that directly supports reducing inflammation and repairing this specific strain.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[prompt],
            config=types.GenerateContentConfig(temperature=0.4) # Lower temperature for clinical accuracy
        )
        return response.text
    except Exception as e:
        return f"Failed to generate recovery protocol: {str(e)}"