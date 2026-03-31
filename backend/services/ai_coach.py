import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Configure Gemini
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def generate_ai_feedback(user_profile, weak_topics):
    """
    Generates coaching feedback using Gemini.
    """

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI Coach is currently unavailable. Please configure GOOGLE_API_KEY or GEMINI_API_KEY in your .env file."

    prompt = f"""
You are a competitive programming mentor.

A student has the following profile:

Rating: {user_profile['rating']}

Weak topics (sorted by priority):
"""

    for topic in weak_topics:
        prompt += f"""
- {topic['topic']}:
    gap: {topic['gap']}
    priority: {topic['priority']}
    solve rate: {topic.get('contest_solve_rate', 'N/A')}
"""

    prompt += """

Give:
1. Clear explanation of weaknesses
2. What topics to focus on first
3. Study strategy (how to improve)
4. Contest strategy
5. Mistakes to avoid
6. Answer in short

Keep it practical and concise.
"""

    try:
        # Dynamically find a model that supports generateContent
        available_models = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        if not available_models:
            return "AI Feedback could not be generated: No compatible models found for this API key."
            
        model = genai.GenerativeModel(available_models[0])
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Feedback could not be generated at this time. (Error: {str(e)})"
