import streamlit as st
import requests
import os

API_URL = "http://localhost:8000"
IMAGES_DIR = "images"

st.set_page_config(page_title="Vikram & Vetal Game", layout="wide")

# --- Add custom CSS for scrollable chat ---
st.markdown("""
    <style>
    .scrollable-chat {
        height: 300px;
        overflow-y: auto;
        background-color: #f9f9f9;
        padding: 1em;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 1em;
    }
    </style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if "story" not in st.session_state:
    resp = requests.post(f"{API_URL}/start_game")
    st.session_state.story = resp.json()
    st.session_state.chat_history = []
    st.session_state.stage = "story"
    st.session_state.last_result = None

story = st.session_state.story

# --- Image Size Configuration ---
IMAGE_WIDTH = 200  # Set the desired image width

# --- Top Section: Narration at the top center ---
st.markdown("<h2 style='text-align: center;'>The Tale of Vikram and Vetal</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center;'><strong>Narration:</strong> {story['narration']}</p>", unsafe_allow_html=True)
# --- Layout: Two columns ---
left_col, right_col = st.columns([2, 1])

with left_col:
    st.markdown("### Vikram & Vetal Conversation")
    chat_html = "<div class='scrollable-chat' id='scrollable-chat'>"
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            chat_html += f"<div><b>Vikram:</b> {msg['content']}</div>"
        else:
            chat_html += f"<div><b>Vetal:</b> {msg['content']}</div>"
    chat_html += "<div id='chat-bottom'></div></div>"
    st.markdown(chat_html, unsafe_allow_html=True)

    st.markdown("""
        <script>
            const chatBox = window.parent.document.getElementById('scrollable-chat');
            if (chatBox) {
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        </script>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"**Vetal's Riddle:** {story['riddle']}")

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Ask Vetal for a hint or discuss the riddle:")
        chat_submitted = st.form_submit_button("Send")

    if chat_submitted and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        chat_req = {
            "story_id": story["id"],
            "messages": st.session_state.chat_history,
            "model": "gpt-4.1",
            "max_tokens": 300,
            "temperature": 0.5
        }
        resp = requests.post(f"{API_URL}/chat", json=chat_req)
        if resp.status_code == 200:
            vetal_reply = resp.json()["response"]
            st.session_state.chat_history.append({"role": "assistant", "content": vetal_reply})
            st.rerun()
        else:
            st.error("Error communicating with Vetal.")

    st.markdown("---")
    with st.form("answer_form", clear_on_submit=True):
        answer = st.text_input("Your answer to the riddle:")
        answer_submitted = st.form_submit_button("Send")

    if answer_submitted and answer:
        answer_req = {
            "story_id": story["id"],
            "answer": answer,
            "chat_history": st.session_state.chat_history
        }
        resp = requests.post(f"{API_URL}/next_stage", json=answer_req)
        if resp.status_code == 200:
            result = resp.json()
            if result["result"] == "correct":
                st.success("Correct! Moving to the next riddle...")
                st.session_state.story = result["next_story"]
                st.session_state.chat_history = []
                st.rerun()
            elif result["result"] == "finished":
                st.balloons()
                st.success(result["message"])
                st.session_state.stage = "end"
            else:
                st.error(result["message"])
                st.session_state.stage = "dead"
        else:
            st.error("Error submitting answer.")

    if st.session_state.stage == "end":
        if st.button("Restart Game"):
            resp = requests.post(f"{API_URL}/start_game")
            st.session_state.story = resp.json()
            st.session_state.chat_history = []
            st.session_state.stage = "story"
            st.rerun()

    if st.session_state.stage == "dead":
        st.warning("You have failed. Try again!")
        if st.button("Restart from Beginning"):
            resp = requests.post(f"{API_URL}/start_game")
            st.session_state.story = resp.json()
            st.session_state.chat_history = []
            st.session_state.stage = "story"
            st.rerun()

with right_col:
    st.markdown(f"**Role:** {story['role'].capitalize()}")
    st.markdown(f"**Context:** {story['context']}")

    # Carousel Implementation
    if story.get("story_images"):
        image_paths = [os.path.join(IMAGES_DIR, img) for img in story["story_images"]]
        existing_images = [img_path for img_path in image_paths if os.path.exists(img_path)]

        if existing_images:
            # Use columns to create a horizontal scrollable layout
            num_images = len(existing_images)
            cols = st.columns(num_images)

            for i, img_path in enumerate(existing_images):
                with cols[i]:
                    st.image(img_path, width=IMAGE_WIDTH)
        else:
            st.write(":ghost: (Images not found)")
    else:
        st.write(":ghost: (No images for this story)")
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
        "X-Api-Key": "<you llm api key>",
        "Content-Type": "application/json"
    }
    context = ssl.create_default_context()
    context.load_verify_locations("./ca-bundle.crt")
    client = httpx.Client(verify=context, headers=headers)
    return AzureOpenAI(
        api_key="<<you llm api key>>",
        http_client=client,
        azure_endpoint='<your llm api endpoint>',
        azure_deployment="<your deployment version>", #example gpt-4.1@2025-04-14
        api_version='<you api version>' #2024-10-21
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

