# 🧠 VoiceCompanionAI, Raspberry Pi AI Voice Buddy

**VoiceCompanionAI** is a production-architected conversational AI system deployed on Raspberry Pi hardware, designed to function as a long-term voice companion.

Inspired by Portal-style AI personalities, Companion is not a basic voice assistant. It is built to feel present, emotionally aware, memory-driven, and adaptive over time.

This project demonstrates full-stack AI systems engineering across edge devices, cloud orchestration, conversational memory, and personality modeling.

---

## ✨ Project Vision

Build an AI companion that can,

- Capture voice conversations in real time
- Transcribe speech via cloud STT
- Generate contextual LLM responses
- Speak replies through TTS
- Maintain long-term memory
- Learn user preferences
- Detect emotional tone
- Adapt personality traits
- Initiate proactive interactions

Think, **Smart toy + conversational agent + memory system**.

---

## 🏗️ System Architecture

```
Raspberry Pi Device Agent
        ↓
FastAPI Orchestrator API
        ↓
Background Worker
        ↓
PostgreSQL + pgvector Memory Layer
        ↓
OpenAI Services (STT, LLM, TTS, Embeddings)
```

---

## 🧱 Service Responsibilities

### Device Agent

- Microphone capture  
- Push-to-talk or wake trigger  
- Audio buffering  
- Network retry handling  
- TTS playback via speaker  

### Orchestrator API

- Device authentication  
- Interaction ingestion  
- Prompt assembly  
- Memory retrieval  
- Job queue insertion  
- Response storage  
- Audio serving endpoints  

### Background Worker

- Speech-to-text processing  
- LLM completion  
- Text-to-speech synthesis  
- Memory extraction  
- Embedding generation  
- Profile summarization  
- Emotion detection  
- Observability logging  

---

## 🧠 Companion Intelligence

The system models long-term familiarity through,

- Conversational history tracking  
- Preference learning  
- Relationship memory  
- Emotional context awareness  
- Personality adaptation  
- Mode-based behaviors  

---

## 🎭 Personality System

Companion personality is configurable and evolves over time.

### Bot Profile Traits

```json
{
  "warmth": 0.9,
  "humor": 0.7,
  "curiosity": 0.8,
  "energy": 0.6,
  "verbosity": 0.4
}
```

Voice commands can dynamically update traits,

- “Be funnier”
- “Talk shorter”
- “Switch to bedtime mode”

All changes persist in the `bot_profiles` table.

---

## 💬 Interaction Modes

Behavior overlays include,

- Storytelling Mode  
- Quiz Mode  
- Bedtime Mode  
- Encouragement Mode  
- Passive Check-ins  

Modes influence prompt tone, pacing, and response style.

---

## ❤️ Emotion Detection

The system analyzes emotional signals from interactions.

### Detection Sources

- Voice tone analysis (audio sentiment)  
- Transcript sentiment fallback  

### Stored Signals

- Emotion label  
- Confidence score  
- Emotional context memory  

Emotion influences,

- Memory salience scoring  
- Prompt tone injection  
- Companion response style  

---

## 🧩 Data and Memory Layer

Built on **PostgreSQL + pgvector**.

### Core Tables

- `users`
- `devices`
- `conversations`
- `interactions`
- `memories`
- `memory_embeddings`
- `user_profiles`
- `bot_profiles`
- `jobs`
- `events`

### Memory Features

- Vector embeddings  
- Salience scoring  
- Emotional tagging  
- Retrieval ranking  

---

## 🔁 Job Queue System

Database-backed async worker pipeline.

### Features

- `SELECT … FOR UPDATE SKIP LOCKED` job claiming  
- Retry tracking  
- Exponential backoff  
- Status transitions  
- Observability events  

### Job Types

- `PROCESS_VOICE_INTERACTION`
- `SUMMARIZE_PROFILE`
- `PROACTIVE_CHECKIN`

---

## 🔊 Voice Pipeline

```
Audio Capture → Upload → STT → LLM → TTS → Playback
```

Latency and processing metrics are stored per interaction for observability.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/voice-interactions` | Upload voice input |
| GET | `/v1/interactions/latest` | Retrieve latest interaction |
| GET | `/v1/audio/{id}.wav` | Fetch generated audio |
| GET | `/health` | Service health check |

Optional extensions include bot profile retrieval and configuration endpoints.

---

## 🐳 Infrastructure

Dockerized multi-service environment,

- FastAPI API container  
- Background worker container  
- PostgreSQL + pgvector  
- Shared audio storage volume  

Run locally,

```bash
docker-compose up --build
```

---

## 🧪 Testing Coverage

Includes validation for,

- Prompt assembly  
- Job locking behavior  
- Memory extraction  
- Emotion detection  
- Personality parsing  

---

## 🛠️ Tech Stack

### Backend

- Python 3.11+  
- FastAPI  
- Async SQLAlchemy  
- Alembic  

### AI Services

- OpenAI Speech-to-Text  
- OpenAI LLM  
- OpenAI Text-to-Speech  
- OpenAI Embeddings  

### Data Layer

- PostgreSQL  
- pgvector  

### Edge Device

- Raspberry Pi  
- PyAudio or sounddevice  

### Infrastructure

- Docker Compose  

---

## 🚀 Portfolio Value

This project demonstrates,

- Edge + cloud orchestration  
- Conversational AI systems  
- Voice pipelines  
- Long-term memory modeling  
- Personality systems  
- Emotion-aware agents  
- Async worker architecture  

---

## 🔮 Future Extensions

Planned roadmap items,

- Vision recognition (camera integration)  
- Growth timeline summaries  
- Parent or admin dashboard  
- Offline inference fallback  
- Multi-user household support  

---

## 📜 License

MIT, intended for educational, research, and portfolio demonstration use.

---

**VoiceCompanionAI** represents the convergence of conversational AI, edge computing, and emotionally intelligent agent systems deployed on consumer hardware.
