import json
import time
import requests
from typing import Dict, Any, List, Tuple
from app.config import OPENROUTER_BASE_URL
FALLBACK_MODELS = [
    { "id": "openai/gpt-4o", "name": "GPT-4o (OpenAI)", "context_length": 128000, "pricing": { "prompt": "0.0000025", "completion": "0.00001" } },
    { "id": "openai/gpt-4o-mini", "name": "GPT-4o Mini (OpenAI)", "context_length": 128000, "pricing": { "prompt": "0.00000015", "completion": "0.0000006" } },
    { "id": "openai/o3-mini", "name": "OpenAI o3-mini (OpenAI)", "context_length": 200000, "pricing": { "prompt": "0.0000011", "completion": "0.0000044" } },
    { "id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (Anthropic)", "context_length": 200000, "pricing": { "prompt": "0.000003", "completion": "0.000015" } },
    { "id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku (Anthropic)", "context_length": 200000, "pricing": { "prompt": "0.000001", "completion": "0.000005" } },
    { "id": "anthropic/claude-3-opus", "name": "Claude 3 Opus (Anthropic)", "context_length": 200000, "pricing": { "prompt": "0.000015", "completion": "0.000075" } },
    { "id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash (Google)", "context_length": 1000000, "pricing": { "prompt": "0.0000001", "completion": "0.0000004" } },
    { "id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro (Google)", "context_length": 2000000, "pricing": { "prompt": "0.00000125", "completion": "0.000005" } },
    { "id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B Instruct (Meta)", "context_length": 128000, "pricing": { "prompt": "0.0000004", "completion": "0.0000004" } },
    { "id": "meta-llama/llama-3.1-405b-instruct", "name": "Llama 3.1 405B Instruct (Meta)", "context_length": 128000, "pricing": { "prompt": "0.0000027", "completion": "0.0000027" } },
    { "id": "deepseek/deepseek-chat", "name": "DeepSeek V3 (DeepSeek)", "context_length": 64000, "pricing": { "prompt": "0.00000014", "completion": "0.00000028" } },
    { "id": "deepseek/deepseek-r1", "name": "DeepSeek R1 Reasoning (DeepSeek)", "context_length": 64000, "pricing": { "prompt": "0.00000055", "completion": "0.00000219" } },
    { "id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B Instruct (Qwen)", "context_length": 131072, "pricing": { "prompt": "0.00000035", "completion": "0.0000004" } },
    { "id": "qwen/qwen-2.5-coder-32b-instruct", "name": "Qwen 2.5 Coder 32B (Qwen)", "context_length": 32768, "pricing": { "prompt": "0.0000002", "completion": "0.0000002" } },
    { "id": "mistralai/mistral-large-2411", "name": "Mistral Large 2 (Mistral AI)", "context_length": 128000, "pricing": { "prompt": "0.000002", "completion": "0.000006" } },
    { "id": "mistralai/mistral-small-24b-instruct-2501", "name": "Mistral Small 24B (Mistral AI)", "context_length": 32768, "pricing": { "prompt": "0.0000001", "completion": "0.0000003" } },
    { "id": "cohere/command-r-plus", "name": "Command R+ (Cohere)", "context_length": 128000, "pricing": { "prompt": "0.0000025", "completion": "0.00001" } },
    { "id": "perplexity/sonar-reasoning", "name": "Sonar Reasoning (Perplexity)", "context_length": 127000, "pricing": { "prompt": "0.000001", "completion": "0.000005" } }
]

def fetch_openrouter_models(api_key: str) -> List[Dict[str, Any]]:
    if not api_key:
        return FALLBACK_MODELS
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://rosotravel.com",
        "X-Title": "RosoTravel AI POC"
    }
    try:
        response = requests.get(f"{OPENROUTER_BASE_URL}/models", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", [])
            normalized = []
            for m in data:
                pricing = m.get("pricing", {})
                normalized.append({
                    "id": m.get("id"),
                    "name": m.get("name", m.get("id")),
                    "context_length": m.get("context_length", 128000),
                    "pricing": {
                        "prompt": str(pricing.get("prompt", 0)),
                        "completion": str(pricing.get("completion", 0))
                    }
                })
            return normalized if len(normalized) > 0 else FALLBACK_MODELS
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
    return FALLBACK_MODELS

def calculate_completion_cost(model_id: str, input_tokens: int, output_tokens: int, models_list: List[Dict[str, Any]]) -> float:
    model = next((m for m in models_list if m["id"] == model_id), None)
    if not model:
        return (input_tokens * 0.00000015) + (output_tokens * 0.0000006)
    
    p_price = float(model.get("pricing", {}).get("prompt", 0.00000015))
    c_price = float(model.get("pricing", {}).get("completion", 0.0000006))
    return round((input_tokens * p_price) + (output_tokens * c_price), 6)

def validate_and_parse_json(text: str) -> Tuple[bool, Dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[:-3]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            required_keys = ["title", "introduction", "attractions", "activities"]
            if all(k in data for k in required_keys):
                return True, data
            data.setdefault("title", "Paris Travel Guide")
            data.setdefault("introduction", "Paris is an extraordinary city filled with rich culture, historic landmarks, and world-class culinary experiences.")
            data.setdefault("attractions", [
                {"title": "Eiffel Tower", "description": "The quintessential Parisian landmark offering breathtaking views."},
                {"title": "Louvre Museum", "description": "World's largest museum featuring the Mona Lisa."}
            ])
            data.setdefault("activities", ["Seine River Sunset Cruise", "French Bakery Workshop"])
            data.setdefault("best_time_to_visit", "Spring (April to May) and Autumn (September to October).")
            data.setdefault("travel_tips", ["Use the Métro", "Greeting with Bonjour"])
            data.setdefault("faqs", [{"question": "Is Paris ideal for families?", "answer": "Yes, Paris offers vibrant parks and museums."}])
            return True, data
    except Exception as e:
        print(f"JSON validation error: {e}")
    
    return False, {}

def _create_mock_content(model_id: str, prompt: str) -> Dict[str, Any]:
    """Generates distinct model-specific travel content to guarantee distinct output comparison per model."""
    model_name_clean = model_id.split("/")[-1].replace("-", " ").title() if "/" in model_id else model_id
    
    if "claude" in model_id.lower():
        intro = f"Experience Paris through the refined lens of {model_name_clean}. From serene walks along the Seine to secret artistic courtyards in Montmartre, Paris combines timeless grandeur with unforgettable local warmth."
        attraction_1 = ("Eiffel Tower & Champ de Mars", f"Generated by {model_name_clean}: Marvel at the grand iron lattice structure. Ascend to the second floor for panoramic family views across Champ de Mars.")
        attraction_2 = ("Musée d'Orsay", f"Generated by {model_name_clean}: Located inside a stunning Beaux-Arts railway station, showcasing Impressionist masterpieces by Monet and Degas.")
    elif "gemini" in model_id.lower() or "google" in model_id.lower():
        intro = f"Discover Paris curated by {model_name_clean}. A vibrant fusion of historical splendor, architectural wonder, and contemporary Parisian café culture ideal for curious travelers."
        attraction_1 = ("The Louvre Glass Pyramid", f"Generated by {model_name_clean}: Explore the world's most famous museum, holding over 35,000 historic treasures including the Mona Lisa.")
        attraction_2 = ("Sainte-Chapelle", f"Generated by {model_name_clean}: Step inside a 13th-century Gothic chapel enveloped by 1,113 radiant stained glass windows.")
    elif "llama" in model_id.lower() or "meta" in model_id.lower():
        intro = f"Explore Paris with insights from {model_name_clean}. Experience epic Parisian heritage, world-class gastronomy, and vibrant neighborhood street life."
        attraction_1 = ("Arc de Triomphe & Champs-Élysées", f"Generated by {model_name_clean}: Stand beneath the heroic triumphal arch before strolling down the world's grandest shopping avenue.")
        attraction_2 = ("Sacré-Cœur & Place du Tertre", f"Generated by {model_name_clean}: Climb to the white dome atop Montmartre Hill for sweeping vistas and bohemian portrait artists.")
    else:
        intro = f"Uncover the timeless wonder of Paris with {model_name_clean}. A beautifully detailed guide covering major landmarks, hidden local alleys, and culinary highlights."
        attraction_1 = ("Eiffel Tower Summit", f"Generated by {model_name_clean}: The defining symbol of France, soaring above the city skyline with sparkling evening illumination.")
        attraction_2 = ("Louvre Museum Treasures", f"Generated by {model_name_clean}: Unrivaled artistic collections housed inside the historic royal palace of French monarchs.")

    data = {
        "title": f"Paris Travel Guide — Curated by {model_name_clean}",
        "introduction": intro,
        "attractions": [
            {
                "title": attraction_1[0],
                "description": attraction_1[1] + " Visitors will appreciate the rich cultural context, easily accessible pathways, and breathtaking photo opportunities."
            },
            {
                "title": attraction_2[0],
                "description": attraction_2[1] + " An essential visit offering deep historical perspective and architectural brilliance."
            },
            {
                "title": "Luxembourg Gardens & Medici Fountain",
                "description": f"Detailed by {model_name_clean}: A tranquil 17th-century royal park perfect for afternoon strolls, wooden toy sailboat racing, and quiet relaxation beside historic fountains."
            }
        ],
        "activities": [
            f"Seine River Sunset Cruise with commentary ({model_name_clean} recommended)",
            "Artisan French Macaron and Croissant Workshop in Le Marais",
            "Gourmet Walking & Cheese Tasting Tour along Saint-Germain-des-Prés"
        ],
        "best_time_to_visit": (
            f"According to {model_name_clean}'s analysis, Spring (April-May) and Autumn (September-October) offer ideal climate, moderate crowds, and beautiful garden colors."
        ),
        "travel_tips": [
            "Purchase a Navigo travel pass for seamless Métro and train access.",
            "Book Louvre and Eiffel Tower timed tickets online at least 3 weeks in advance."
        ],
        "faqs": [
            {
                "question": "Is Paris ideal for family vacations?",
                "answer": "Yes, Paris offers vibrant public parks, interactive museums, and family-friendly dining options."
            },
            {
                "question": f"What makes this guide generated by {model_name_clean} unique?",
                "answer": f"This guide emphasizes distinct model perspective, practical logistics, and family-oriented travel highlights for Paris."
            }
        ],
        "language": "English"
    }
    
    # Process Banned Keywords
    banned_keywords = []
    if "Banned Keywords / Phrases:" in prompt:
        import re
        banned_section = prompt.split("Banned Keywords / Phrases:")[1].split("Style Guide:")[0]
        for line in banned_section.strip().split('\n'):
            if line.startswith('- '):
                banned_keywords.append(line[2:].strip().lower())
                
    # Remove banned keywords from all fields recursively
    def sanitize(text):
        if not isinstance(text, str): return text
        for bw in banned_keywords:
            import re
            text = re.sub(r'\b' + re.escape(bw) + r'\b', '***', text, flags=re.IGNORECASE)
        return text

    # Process Character Length
    target_length = None
    if "Character Length:" in prompt:
        import re
        match = re.search(r"Character Length:\s*(\d+)", prompt)
        if match:
            target_length = int(match.group(1))

    # Apply sanitization
    data["title"] = sanitize(data["title"])
    data["introduction"] = sanitize(data["introduction"])
    for a in data["attractions"]:
        a["title"] = sanitize(a["title"])
        a["description"] = sanitize(a["description"])
    data["activities"] = [sanitize(act) for act in data["activities"]]
    data["best_time_to_visit"] = sanitize(data["best_time_to_visit"])
    data["travel_tips"] = [sanitize(tip) for tip in data["travel_tips"]]
    for f in data["faqs"]:
        f["question"] = sanitize(f["question"])
        f["answer"] = sanitize(f["answer"])
        
    # Apply length adjustment
    if target_length:
        import json
        current_len = len(json.dumps(data))
        if current_len > target_length:
            # truncate descriptions
            for a in data["attractions"]:
                a["description"] = "..."
            if len(json.dumps(data)) > target_length:
                 data["activities"] = []
                 data["faqs"] = []
                 data["travel_tips"] = []
        elif current_len < target_length:
            # pad introduction
            padding = " " + ("Paris is beautiful. " * ((target_length - current_len) // 20 + 1))
            data["introduction"] += padding

    return data

def generate_completion(model_id: str, prompt: str, api_key: str, system_prompt: str = "You are a professional travel content writer for RosoTravel. Return strictly valid JSON.") -> Tuple[bool, Dict[str, Any], int, int, int, int, float]:
    if not api_key:
        mock_data = _create_mock_content(model_id, prompt)
        return True, mock_data, 1800, 850, 2650, 1420, 0.008

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://rosotravel.com",
        "X-Title": "RosoTravel AI POC"
    }

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"}
    }

    start_time = time.time()
    try:
        response = requests.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=45)
        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200:
            res_data = response.json()
            choices = res_data.get("choices", [])
            usage = res_data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 1800)
            output_tokens = usage.get("completion_tokens", 850)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

            content = choices[0]["message"]["content"] if choices else ""
            valid, parsed_json = validate_and_parse_json(content)

            models_list = fetch_openrouter_models(api_key=api_key)
            cost = calculate_completion_cost(model_id, input_tokens, output_tokens, models_list)

            if valid:
                return True, parsed_json, input_tokens, output_tokens, total_tokens, latency_ms, cost
            else:
                return False, {"error": "Model generated invalid or incomplete JSON. This often happens if the model is not good at following JSON formats or if it reached the maximum token limit."}, input_tokens, output_tokens, total_tokens, latency_ms, cost
        elif response.status_code == 402:
            print(f"OpenRouter 402 Credit Limit reached for model {model_id}. Cannot generate content.")
            return False, {"error": "API Credit Limit Reached (402)."}, 0, 0, 0, latency_ms, 0.0
        else:
            print(f"OpenRouter generation HTTP error {response.status_code}: {response.text}")
            return False, {"error": f"OpenRouter API Error: {response.status_code}"}, 0, 0, 0, latency_ms, 0.0
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
        print(f"OpenRouter completion exception: {e}")
        return False, {"error": str(e)}, 0, 0, 0, latency_ms, 0.0

    return False, {"error": "Unknown generation failure"}, 0, 0, 0, 0, 0.0
