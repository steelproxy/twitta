import openai
from log import app_logger as logger

def get_chatgpt_response(prompt):
    try:
        response = openai.chat.completions.create(model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}])
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
        else:
            logger.error("No response received from OpenAI.")
            return "Sorry, I couldn't process that."
    except Exception as e:
        logger.error(f"Error getting response from OpenAI: {e}")
        return "Sorry, I couldn't process that."