# 💊 LIFEXIA — Django AI Health Assistant

All-in-one Django app: **Chat**, **Health Grid Map**, **WhatsApp messaging** — no npm, no frontend build tools.

---

## 🚀 Quick Start

```bash
# 1. Clone / copy project
cd lifexia_django

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set your WhatsApp token

# 4. Initialise Django
python manage.py migrate
python manage.py collectstatic --noinput

# 5. Run server
python manage.py runserver

# Open http://127.0.0.1:8000
```

---

## 📁 Project Structure

```
lifexia_django/
├── manage.py
├── requirements.txt
├── .env.example
├── LIFEXIA_PharmaCSV_Generator.ipynb  ← Colab notebook for PDF→CSV
├── data/
│   └── pharma.csv          ← Place generated CSV here
├── lifexia/
│   ├── settings.py         ← All configuration
│   ├── urls.py             ← Root URL routing
│   └── wsgi.py
├── templates/
│   └── index.html          ← Full frontend (no npm needed)
├── apps/
│   ├── chat/               ← AI chat + RAG drug service
│   │   ├── rag_service.py  ← Qwen2.5-3B-Instruct LLM + drug DB
│   │   ├── views.py
│   │   └── urls.py
│   ├── map_grid/           ← Hospital/pharmacy map
│   │   ├── service.py      ← Haversine distance + 15 facilities
│   │   ├── views.py
│   │   └── urls.py
│   └── whatsapp/           ← WhatsApp send-only service
│       ├── service.py      ← Meta Cloud API v22.0
│       ├── views.py
│       └── urls.py
```

---

## ⚙️ Configuration (.env)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | `True` for dev |
| `WHATSAPP_ACCESS_TOKEN` | Meta permanent token |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verify token |
| `LLM_MODEL_NAME` | `Qwen/Qwen2.5-3B-Instruct` |
| `USE_GPU` | `True` if CUDA available |
| `PHARMA_CSV_PATH` | Path to pharma.csv |

---

## 💊 pharma.csv — Pharma Data

Use the included **Colab notebook** `LIFEXIA_PharmaCSV_Generator.ipynb` to:
1. Upload any pharma PDF (NLEM, formulary, drug monographs)
2. Automatically extract drug data with regex or Claude AI
3. Download `pharma.csv`
4. Place in `data/pharma.csv` — loaded automatically on startup

---

## 🌐 API Endpoints

### Chat
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/chat/init` | Start session |
| POST | `/api/chat/message` | Send message, get AI response |
| POST | `/api/chat/drug-search` | Search specific drug |
| GET | `/api/chat/emergency-drugs` | Emergency drug list |

### Map
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/map/locations?lat=X&lng=Y` | All facilities near you |
| GET | `/api/map/hospitals?lat=X&lng=Y` | Nearby hospitals |
| GET | `/api/map/pharmacies?lat=X&lng=Y` | Nearby pharmacies |
| GET | `/api/map/emergency?lat=X&lng=Y` | Emergency hospitals |
| GET | `/api/map/search?q=cardiac` | Search facilities |
| POST | `/api/map/send-directions` | WhatsApp directions |

### WhatsApp
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/whatsapp/send-message` | Send text message |
| POST | `/api/whatsapp/medication-reminder` | Send reminder |
| POST | `/api/whatsapp/emergency-alert` | Send emergency alert |
| POST | `/api/whatsapp/hospital-directions` | Send directions |
| POST | `/api/whatsapp/broadcast` | Broadcast to multiple numbers |
| GET/POST | `/api/whatsapp/webhook` | Meta webhook endpoint |

---

## 🤖 LLM Model

**Qwen/Qwen2.5-3B-Instruct** — downloads automatically from HuggingFace on first run (~6GB).

Chat priority: `pharma.csv` → built-in drug DB → Qwen LLM → fallback

Set `USE_GPU=True` in `.env` if you have a CUDA GPU for faster responses.
# chatbot-classy
