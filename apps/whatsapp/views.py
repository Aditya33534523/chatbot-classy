import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from .service import get_wa

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def send_message(request):
    try:
        data = json.loads(request.body or '{}')
        to = data.get('to_number', '').strip()
        body = data.get('message', '').strip()
        if not to or not body:
            return JsonResponse({"success": False, "error": "to_number and message required"}, status=400)
        return JsonResponse(get_wa().send_text(to, body))
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_template(request):
    try:
        data = json.loads(request.body or '{}')
        to = data.get('to_number', '').strip()
        template = data.get('template_name', '').strip()
        language = data.get('language', 'en')
        components = data.get('components')
        if not to or not template:
            return JsonResponse({"success": False, "error": "to_number and template_name required"}, status=400)
        return JsonResponse(get_wa().send_template(to, template, language, components))
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def medication_reminder(request):
    try:
        data = json.loads(request.body or '{}')
        to = data.get('to_number', '').strip()
        med = data.get('medication_name', '').strip()
        if not to or not med:
            return JsonResponse({"success": False, "error": "to_number and medication_name required"}, status=400)
        return JsonResponse(get_wa().send_medication_reminder(
            to, med, data.get('dosage', ''), data.get('time', '')))
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def emergency_alert(request):
    try:
        data = json.loads(request.body or '{}')
        to = data.get('to_number', '').strip()
        return JsonResponse(get_wa().send_emergency_alert(
            to, data.get('alert_type', ''), data.get('details', ''), data.get('location', '')))
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def hospital_directions(request):
    try:
        data = json.loads(request.body or '{}')
        to = data.get('to_number', '').strip()
        return JsonResponse(get_wa().send_hospital_directions(
            to, data.get('hospital_name', ''), data.get('address', ''),
            data.get('google_maps_link', ''), data.get('distance', 'N/A'), data.get('eta', 'N/A')))
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def broadcast(request):
    """Broadcast to multiple numbers — template or text."""
    try:
        data = json.loads(request.body or '{}')
        numbers = data.get('numbers') or data.get('phone_numbers', [])
        template_name = data.get('template_name')
        components = data.get('components')
        message = data.get('message')

        if not numbers:
            return JsonResponse({"success": False, "error": "numbers required"}, status=400)

        wa = get_wa()
        results = {"total": len(numbers), "sent": 0, "failed": 0, "errors": [], "details": []}

        for num in numbers:
            try:
                if template_name and template_name != 'custom_text':
                    res = wa.send_template(num, template_name, 'en', components)
                elif message:
                    res = wa.send_text(num, message)
                else:
                    res = {"success": False, "error": "No message or template specified"}

                if res.get('success'):
                    results['sent'] += 1
                    results['details'].append({"number": num, "status": "sent", "message_id": res.get('message_id')})
                else:
                    results['failed'] += 1
                    results['errors'].append({"number": num, "error": res.get('error'), "error_code": res.get('error_code')})
                    results['details'].append({"number": num, "status": "failed", "error": res.get('error')})
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({"number": num, "error": str(e)})

        logger.info(f"Broadcast: {results['sent']}/{results['total']} sent")
        return JsonResponse({"success": results['sent'] > 0, "broadcast_result": results})
    except Exception as e:
        logger.error(f"Broadcast error: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def session_status(request, phone_number: str):
    try:
        return JsonResponse({"success": True, "status": get_wa().session_status(phone_number)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# ── Webhook ─────────────────────────────────────────────────────

@csrf_exempt
def webhook(request):
    if request.method == 'GET':
        verify_token = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', '')
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == verify_token:
            logger.info("WhatsApp webhook verified")
            from django.http import HttpResponse
            return HttpResponse(challenge, content_type='text/plain')
        return JsonResponse({"error": "Forbidden"}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
            wa = get_wa()
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    for msg in value.get('messages', []):
                        phone = msg.get('from')
                        if phone:
                            wa.record_incoming(phone)
                        logger.info(f"Incoming WA message from {phone}")
            return JsonResponse({"status": "received"})
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)
