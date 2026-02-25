import json
import uuid
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from .rag_service import get_rag

logger = logging.getLogger(__name__)

# In-memory chat store (per session)
_chat_store: dict = {}


def _get_session_history(session, session_id: str) -> list:
    key = f"chat_{session_id}"
    if key not in session:
        session[key] = []
    return session[key]


def _append(session, session_id: str, role: str, content: str):
    key = f"chat_{session_id}"
    history = session.get(key, [])
    history.append({"role": role, "content": content, "ts": datetime.now().isoformat()})
    session[key] = history[-40:]  # keep last 40


def index_view(request):
    return render(request, 'index.html')


@csrf_exempt
@require_http_methods(["POST"])
def init_chat(request):
    try:
        data = json.loads(request.body or '{}')
        session_id = request.session.get('chat_session_id') or str(uuid.uuid4())
        request.session['chat_session_id'] = session_id
        return JsonResponse({
            "success": True,
            "session_id": session_id,
            "welcome_message": (
                "Welcome to **LIFEXIA**! I'm your AI health assistant.\n\n"
                "I can help with:\n"
                "- 💊 **Drug Information** — Dosages, side effects, interactions\n"
                "- 🏥 **Nearby Hospitals** — Use the Health Grid map\n"
                "- 🚨 **Emergency Help** — Quick emergency contacts\n"
                "- 📱 **WhatsApp** — Send info to your phone\n\n"
                "How can I assist you today?"
            ),
        })
    except Exception as e:
        logger.error(f"init_chat error: {e}")
        return JsonResponse({"success": True, "session_id": "default",
                             "welcome_message": "Welcome to LIFEXIA!"})


@csrf_exempt
@require_http_methods(["POST"])
def message(request):
    try:
        data = json.loads(request.body or '{}')
        user_msg = data.get('message', '').strip()
        user_email = data.get('user_email', 'anonymous')
        session_id = data.get('session_id') or request.session.get('chat_session_id') or str(uuid.uuid4())
        user_type = data.get('user_type', request.session.get('user_type', 'patient'))

        if not user_msg:
            return JsonResponse({"success": False, "error": "Message is required"}, status=400)

        request.session['chat_session_id'] = session_id
        rag = get_rag()
        response_text = rag.query(user_msg, user_type)

        _append(request.session, session_id, 'user', user_msg)
        _append(request.session, session_id, 'assistant', response_text)

        # Store in global chat store keyed by email
        if user_email not in _chat_store:
            _chat_store[user_email] = {}
        if session_id not in _chat_store[user_email]:
            _chat_store[user_email][session_id] = {
                "id": len(_chat_store[user_email]) + 1,
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "messages": [],
            }
        conv = _chat_store[user_email][session_id]
        conv["messages"].append({"role": "user", "content": user_msg, "ts": datetime.now().isoformat()})
        conv["messages"].append({"role": "assistant", "content": response_text, "ts": datetime.now().isoformat()})

        return JsonResponse({
            "success": True,
            "response": response_text,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"message error: {e}", exc_info=True)
        return JsonResponse({"success": False, "response": "Error processing request.", "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def query(request):
    """Legacy endpoint for chat.html"""
    try:
        data = json.loads(request.body or '{}')
        user_msg = data.get('message', '').strip()
        user_type = data.get('user_type', 'patient')
        if not user_msg:
            return JsonResponse({"success": False, "error": "Message required"}, status=400)
        rag = get_rag()
        response_text = rag.query(user_msg, user_type)
        return JsonResponse({"success": True, "response": response_text,
                             "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"query error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def drug_search(request):
    try:
        data = json.loads(request.body or '{}')
        name = data.get('drug_name', '').strip()
        user_type = data.get('user_type', 'patient')
        if not name:
            return JsonResponse({"success": False, "error": "Drug name required"}, status=400)
        rag = get_rag()
        drug = rag.search_drug(name)
        if drug:
            return JsonResponse({
                "success": True, "found": True,
                "drug_info": {"name": drug['name'], "category": drug.get('category'), "use": drug.get('use')},
                "formatted_response": rag.format_drug(drug, user_type),
            })
        return JsonResponse({"success": True, "found": False,
                             "message": f'No information found for "{name}".'})
    except Exception as e:
        logger.error(f"drug_search error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def emergency_drugs(request):
    try:
        rag = get_rag()
        drugs = rag.emergency_drugs()
        return JsonResponse({
            "success": True,
            "drugs": [{"name": d['name'], "category": d.get('category'), "use": d.get('use', '')[:120] + '...'}
                      for d in drugs],
            "categories": rag.all_categories(),
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def quick_info(request, drug_name: str):
    try:
        rag = get_rag()
        drug = rag.search_drug(drug_name)
        if drug:
            return JsonResponse({
                "success": True,
                "drug": {"name": drug['name'], "generic": drug.get('generic'),
                         "dosage": drug.get('dosage'), "warnings": drug.get('warning'), "use": drug.get('use')},
            })
        return JsonResponse({"success": False, "error": "Drug not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def history(request):
    try:
        session_id = request.session.get('chat_session_id', '')
        chat_history = request.session.get(f"chat_{session_id}", [])
        return JsonResponse({"success": True, "history": chat_history, "count": len(chat_history)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_history(request):
    try:
        session_id = request.session.get('chat_session_id', '')
        if session_id:
            request.session[f"chat_{session_id}"] = []
        return JsonResponse({"success": True, "message": "Chat history cleared"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ── User Chat History for sidebar ────────────────────────────────

@require_http_methods(["GET"])
def user_history(request, user_email: str):
    convs = _chat_store.get(user_email, {})
    result = []
    for sid, conv in convs.items():
        msgs = conv.get('messages', [])
        result.append({
            "id": conv.get('id'),
            "session_id": sid,
            "title": (msgs[0]['content'][:40] if msgs else "Untitled"),
            "last_message": (msgs[-1]['content'][:80] if msgs else ""),
            "created_at": conv.get('created_at'),
        })
    return JsonResponse(result, safe=False)


@require_http_methods(["GET"])
def conversation_detail(request, session_id: str):
    for user_convs in _chat_store.values():
        if session_id in user_convs:
            conv = user_convs[session_id]
            return JsonResponse({"session_id": session_id, "messages": conv.get('messages', [])})
    return JsonResponse({"error": "Not found", "messages": []}, status=404)
