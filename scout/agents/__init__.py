from dotenv import load_dotenv
import os
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.models.groq import GroqModel

load_dotenv(".env")
model = GroqModel(
    model_name="openai/gpt-oss-20b",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY")),
)
