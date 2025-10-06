from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import ssl
from openai import AzureOpenAI
import json
import os

# ---- LLM Client Initialization ----
def init_openai_client():
    headers = {
        "X-Api-Key": "<your llm api key>",
        "Content-Type": "application/json"
    }
    context = ssl.create_default_context()
    context.load_verify_locations("./ca-bundle.crt")
    client = httpx.Client(verify=context, headers=headers)
    return AzureOpenAI(
        api_key="<your llm api key>",
        http_client=client,
        azure_endpoint='<your llm api endpoint>',
        azure_deployment="<your azure deployment version>", #example gpt-4.1@2025-04-14
        api_version='<your llm api version>' #example 2024-10-21
    )

client = init_openai_client()

# ---- FastAPI Setup ----
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Data Models ----
class Message(BaseModel):
    role: str
    content: str
    image_b64: Optional[str] = None

class ChatRequest(BaseModel):
    story_id: int
    messages: List[Message]
    model: str = "gpt-4.1"
    max_tokens: int = 500
    temperature: float = 0.5

class AnswerRequest(BaseModel):
    story_id: int
    answer: str
    chat_history: List[Message]

# ---- Load Stories ----
STORIES_FILE = os.environ.get("STORIES_FILE", "stories.json")
with open(STORIES_FILE, "r") as f:
    STORIES = json.load(f)["stories"]

def get_story_by_id(story_id):
    for s in STORIES:
        if s["id"] == story_id:
            return s
    return None

def get_next_story(current_id):
    idx = next((i for i, s in enumerate(STORIES) if s["id"] == current_id), None)
    if idx is not None and idx + 1 < len(STORIES):
        return STORIES[idx + 1]
    return None

# ---- API Endpoints ----

@app.get("/")
async def read_root():
    return {"message": "Vikram & Vetal Game Backend is running."}

@app.post("/start_game")
async def start_game():
    return STORIES[0]

@app.post("/next_stage")
async def next_stage(req: AnswerRequest):
    story = get_story_by_id(req.story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    if req.answer.strip().lower() == story["answer"].strip().lower():
        next_story = get_next_story(story["id"])
        if next_story:
            return {"result": "correct", "next_story": next_story}
        else:
            return {"result": "finished", "message": "Congratulations! You have completed all stories."}
    else:
        return {"result": "wrong", "message": "Vikram has died! Try again."}

@app.post("/chat")
async def chat_completion(request: ChatRequest):
    story = get_story_by_id(request.story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    # Persona prompt for Vetal in the current role
    persona = (
        f"You are Vetal, a {story['role']}. "
        f"Here is the context: {story['context']} "
        f"Here is the riddle or question: {story['riddle']} "
        "Have a conversation with Vikram (the player). "
        "Give hints and discuss the problem, but do NOT reveal the answer directly. "
        "Stay in character for your role."
    )
    # Build messages for LLM
    messages = [{"role": "system", "content": persona}]
    for m in request.messages:
        messages.append({"role": m.role, "content": m.content})
    try:
        response = client.chat.completions.create(
            model=request.model,
            messages=messages,
            max_completion_tokens=request.max_tokens,
            temperature=request.temperature
        )
        assistant_message = response.choices[0].message.content
        return {"response": assistant_message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

@app.get("/get_story/{story_id}")
async def get_story(story_id: int):
    story = get_story_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found.")
    return story

