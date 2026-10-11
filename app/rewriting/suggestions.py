from app.core.llm_client import call_json_model
from app.rewriting.prompts import rewrite_prompt
from app.rewriting.schemas import RewriteOutput


async def suggest(context, original, instruction):
    system, user = rewrite_prompt(context, original, instruction)
    return await call_json_model(user, RewriteOutput, max_tokens=3000, system=system)
