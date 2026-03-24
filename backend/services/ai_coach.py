import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

def generate_ai_feedback(user_profile, weak_topics):
    """
    Generates coaching feedback using Gemini.
    """

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
    solve rate: {topic['contest_solve_rate']}
"""

    prompt += """

Give:
1. Clear explanation of weaknesses
2. What topics to focus on first
3. Study strategy (how to improve)
4. Contest strategy
5. Mistakes to avoid

Keep it practical and concise.
"""

    response = model.generate_content(prompt)

    return response.text