from dotenv import load_dotenv
import os

from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.google import GoogleModel

load_dotenv(".env")
# model = GroqModel(
#     model_name="openai/gpt-oss-20b",
#     provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY")),
# )

# HACK: have your api keys separate via comma
api_keys = os.environ.get("GOOGLE_API_KEY", "").split(",")
gemini_model = os.environ.get("SCOUT_GEMINI_MODEL", "gemini-flash-latest").strip()

models = [
    GoogleModel(gemini_model, provider=GoogleProvider(api_key=key.strip()))
    for key in api_keys
    if key and key.strip()
]

model = FallbackModel(*models) if models else None
