import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .service import get_map

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def all_locations(request):
    try:
        ulat = request.GET.get('lat')
        ulng = request.GET.get('lng')
        category = request.GET.get('category', 'ALL RESOURCES')
        lat = float(ulat) if ulat else None
        lng = float(ulng) if ulng else None
        data = get_map().all_locations(lat, lng, category)
        return JsonResponse({"success": True, "facilities": data, "count": len(data)})
    except Exception as e:
        logger.error(f"all_locations error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def nearby_hospitals(request):
    try:
        ulat = float(request.GET.get('lat', 23.0258))
        ulng = float(request.GET.get('lng', 72.5873))
        radius = float(request.GET.get('radius', 20))
        speciality = request.GET.get('speciality')
        ayushman = request.GET.get('ayushman') == 'true'
        maa = request.GET.get('maa') == 'true'
        emergency = request.GET.get('emergency') == 'true'
        data = get_map().nearby_hospitals(ulat, ulng, radius, speciality, ayushman, maa, emergency)
        return JsonResponse({"success": True, "hospitals": data, "count": len(data),
                             "user_location": {"lat": ulat, "lng": ulng}})
    except Exception as e:
        logger.error(f"nearby_hospitals error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def nearby_pharmacies(request):
    try:
        ulat = float(request.GET.get('lat', 23.0258))
        ulng = float(request.GET.get('lng', 72.5873))
        radius = float(request.GET.get('radius', 10))
        open_now = request.GET.get('open_now') == 'true'
        data = get_map().nearby_pharmacies(ulat, ulng, radius, open_now)
        return JsonResponse({"success": True, "pharmacies": data, "count": len(data)})
    except Exception as e:
        logger.error(f"nearby_pharmacies error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def emergency_hospitals(request):
    try:
        ulat = request.GET.get('lat')
        ulng = request.GET.get('lng')
        lat = float(ulat) if ulat else None
        lng = float(ulng) if ulng else None
        data = get_map().emergency_hospitals(lat, lng)
        return JsonResponse({"success": True, "hospitals": data, "count": len(data)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def search_facilities(request):
    try:
        query = request.GET.get('q', '').strip()
        ftype = request.GET.get('type')
        if not query:
            return JsonResponse({"success": False, "error": "Query required"}, status=400)
        data = get_map().search(query, ftype)
        return JsonResponse({"success": True, "results": data, "count": len(data)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
def facility_detail(request, facility_id: str):
    try:
        f = get_map().by_id(facility_id)
        if f:
            return JsonResponse({"success": True, "facility": f})
        return JsonResponse({"success": False, "error": "Not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_directions_whatsapp(request):
    """Send hospital directions via WhatsApp."""
    try:
        data = json.loads(request.body or '{}')
        to = data.get('to_number', '').strip()
        fid = data.get('facility_id', '').strip()
        if not to or not fid:
            return JsonResponse({"success": False, "error": "to_number and facility_id required"}, status=400)
        f = get_map().by_id(fid)
        if not f:
            return JsonResponse({"success": False, "error": "Facility not found"}, status=404)

        from apps.whatsapp.service import get_wa
        result = get_wa().send_hospital_directions(
            to, f['name'], f['address'],
            f.get('googleMapsLink', ''),
            f"{f.get('distance', 'N/A')} km",
            f"{f.get('estimatedTime', 'N/A')} min"
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
