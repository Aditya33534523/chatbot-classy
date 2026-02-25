"""
LIFEXIA Map Service — Django Edition
Hospital & Pharmacy location data with distance/filter/search.
"""

import math
import json
import os
import logging
import urllib.parse
from pathlib import Path
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

FACILITIES = [
    {"id":"h001","name":"Elite Orthopaedic & Womens Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Orthopaedic","lat":23.0258,"lng":72.5873,"address":"Navrangpura, Ahmedabad, Gujarat 380009","contact":"+91-79-26560123","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["ICICI Lombard","Star Health","HDFC Ergo"],"services":["Orthopaedic Surgery","Joint Replacement","Gynaecology","Maternity","Emergency"],"certifications":["NABH"],"ratings":4.5,"benefit":"Advanced joint replacement center with robotic-assisted surgery."},
    {"id":"h002","name":"Sannidhya Gynaec Hospital","type":"HOSPITAL","category":"Specialty","speciality":"Gynaecology","lat":23.015,"lng":72.556,"address":"Chekla Goplnagar, Ahmedabad, Gujarat 380015","contact":"+91-79-26340567","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":True,"cashlessCompanies":["Star Health","New India Assurance"],"services":["Gynaecology","Obstetrics","Maternity","IVF","Laparoscopy"],"certifications":[],"ratings":4.3,"benefit":"Specialized women's healthcare. Accepts Ayushman Bharat & MAA Vatsalya cards."},
    {"id":"h003","name":"Khusboo Orthopaedic Hospital","type":"HOSPITAL","category":"Specialty","speciality":"Orthopaedic","lat":23.032,"lng":72.565,"address":"Ghatlodia, Ahmedabad, Gujarat 380061","contact":"+91-79-27430890","emergency":True,"open24x7":False,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["ICICI Lombard","Bajaj Allianz"],"services":["Orthopaedic Surgery","Fracture Treatment","Physiotherapy","Spine Surgery"],"certifications":[],"ratings":4.2,"benefit":"Expert fracture & spine care. Cashless with Ayushman Bharat card."},
    {"id":"h004","name":"Star Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Multispeciality","lat":23.018,"lng":72.57,"address":"Naranpura, Ahmedabad, Gujarat 380013","contact":"+91-79-27560456","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":True,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Max Bupa"],"services":["Cardiology","Neurology","Orthopaedics","Emergency","ICU","Paediatrics"],"certifications":["NABH","NABL"],"ratings":4.6,"benefit":"Full-service multi-specialty hospital. NABH accredited with 24/7 emergency."},
    {"id":"h005","name":"Vanza Hospital","type":"HOSPITAL","category":"General","speciality":"Multispeciality","lat":23.0095,"lng":72.552,"address":"Nava Vadaj, Ahmedabad, Gujarat 380013","contact":"+91-79-29290345","emergency":True,"open24x7":True,"ayushmanCard":False,"maaCard":True,"cashlessCompanies":["New India Assurance"],"services":["General Medicine","Surgery","Maternity","Paediatrics","Emergency"],"certifications":[],"ratings":4.0,"benefit":"Affordable multi-specialty care. MAA Vatsalya card accepted."},
    {"id":"h006","name":"Shreeji Children Hospital","type":"HOSPITAL","category":"Specialty","speciality":"Pediatrics","lat":23.005,"lng":72.548,"address":"Ranip, Ahmedabad, Gujarat 382480","contact":"+91-79-27550198","emergency":True,"open24x7":False,"ayushmanCard":True,"maaCard":True,"cashlessCompanies":["Star Health","ICICI Lombard"],"services":["Paediatrics","Neonatology","Child Surgery","Vaccination"],"certifications":[],"ratings":4.4,"benefit":"Dedicated children's hospital with NICU. Ayushman & MAA cards accepted."},
    {"id":"h007","name":"Civil Hospital Ahmedabad","type":"HOSPITAL","category":"Government","speciality":"Multispeciality","lat":23.045,"lng":72.598,"address":"Asarwa, Ahmedabad, Gujarat 380016","contact":"+91-79-22683721","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":True,"cashlessCompanies":[],"services":["All Specialties","Trauma Center","Emergency","ICU","Blood Bank"],"certifications":["NABH"],"ratings":3.8,"benefit":"Largest government hospital in Gujarat. Free treatment under Ayushman Bharat."},
    {"id":"h008","name":"SAL Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Multispeciality","lat":23.052,"lng":72.535,"address":"Drive-In Road, Ahmedabad, Gujarat 380054","contact":"+91-79-40200200","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Bajaj Allianz","Max Bupa"],"services":["Cardiac Surgery","Neurosurgery","Orthopaedics","Oncology"],"certifications":["NABH","NABL"],"ratings":4.7,"benefit":"Premier multi-specialty hospital. Advanced cardiac care with robotic surgery."},
    {"id":"h009","name":"Zydus Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Multispeciality","lat":23.07,"lng":72.517,"address":"SG Highway, Ahmedabad, Gujarat 380054","contact":"+91-79-66190000","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Bajaj Allianz","Tata AIG"],"services":["Cardiology","Transplant","Oncology","Neurosurgery","Robotics"],"certifications":["NABH","JCI"],"ratings":4.8,"benefit":"JCI accredited. Organ transplant & proton therapy for cancer."},
    {"id":"h010","name":"Apollo Hospital Ahmedabad","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Multispeciality","lat":23.038,"lng":72.509,"address":"Bhat, GIFT City Road, Ahmedabad, Gujarat","contact":"+91-79-66701800","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Bajaj Allianz","Max Bupa","Tata AIG"],"services":["All Specialties","Robotic Surgery","Transplant","Emergency","Heart Center"],"certifications":["NABH","JCI"],"ratings":4.7,"benefit":"Part of Apollo chain. International quality care with 24/7 emergency."},
    {"id":"h011","name":"Shalby Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Orthopaedic","lat":23.013,"lng":72.531,"address":"S.G. Highway, Ahmedabad, Gujarat 380015","contact":"+91-79-40500500","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo"],"services":["Joint Replacement","Spine Surgery","Orthopaedics","Physiotherapy"],"certifications":["NABH"],"ratings":4.5,"benefit":"India's leading joint replacement hospital. 1 lakh+ successful surgeries."},
    {"id":"h012","name":"HCG Cancer Centre","type":"HOSPITAL","category":"Specialty","speciality":"Oncology","lat":23.0405,"lng":72.556,"address":"Mithakali, Ahmedabad, Gujarat 380006","contact":"+91-79-66280000","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Bajaj Allianz"],"services":["Medical Oncology","Radiation Therapy","Chemotherapy","PET Scan","BMT"],"certifications":["NABH"],"ratings":4.6,"benefit":"Specialized cancer centre. Advanced radiation therapy and bone marrow transplant."},
    {"id":"h013","name":"CIMS Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Multispeciality","lat":23.058,"lng":72.535,"address":"Science City Road, Sola, Ahmedabad","contact":"+91-79-27712771","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Max Bupa"],"services":["Cardiology","Neurosurgery","Gastro","Urology","Emergency","ICU"],"certifications":["NABH"],"ratings":4.5,"benefit":"Advanced cardiac care with TAVI. 300+ bed multi-specialty hospital."},
    {"id":"h014","name":"Pramukhswami Eye Hospital","type":"HOSPITAL","category":"Specialty","speciality":"Ophthalmology","lat":23.048,"lng":72.545,"address":"Paldi, Ahmedabad, Gujarat 380007","contact":"+91-79-26550111","emergency":False,"open24x7":False,"ayushmanCard":True,"maaCard":False,"cashlessCompanies":["Star Health"],"services":["Cataract Surgery","LASIK","Glaucoma","Retina Treatment"],"certifications":[],"ratings":4.4,"benefit":"Affordable eye care. Ayushman card accepted for cataract surgery."},
    {"id":"h015","name":"KD Hospital","type":"HOSPITAL","category":"Multi-Specialty","speciality":"Multispeciality","lat":23.06,"lng":72.568,"address":"Vaishnodevi Circle, SG Highway, Ahmedabad","contact":"+91-79-66770000","emergency":True,"open24x7":True,"ayushmanCard":True,"maaCard":True,"cashlessCompanies":["Star Health","ICICI Lombard","HDFC Ergo","Bajaj Allianz"],"services":["All Specialties","Transplant","Emergency","Robotic Surgery","Rehabilitation"],"certifications":["NABH"],"ratings":4.5,"benefit":"State-of-the-art 400-bed hospital. Kidney and liver transplant centre."},
    {"id":"p001","name":"MedPlus Pharmacy - Navrangpura","type":"PHARMACY","category":"Retail Pharmacy","speciality":"Pharmacy","lat":23.028,"lng":72.585,"address":"Navrangpura, Ahmedabad, Gujarat 380009","contact":"+91-79-26560999","emergency":False,"open24x7":False,"ayushmanCard":False,"maaCard":False,"cashlessCompanies":[],"services":["Prescription Medicines","OTC Medicines","Health Products","Home Delivery"],"certifications":[],"ratings":4.1,"benefit":"Trusted pharmacy chain. Home delivery available."},
    {"id":"p002","name":"Apollo Pharmacy - CG Road","type":"PHARMACY","category":"Retail Pharmacy","speciality":"Pharmacy","lat":23.03,"lng":72.562,"address":"CG Road, Ahmedabad, Gujarat 380006","contact":"+91-79-26460333","emergency":False,"open24x7":True,"ayushmanCard":False,"maaCard":False,"cashlessCompanies":[],"services":["Prescription Medicines","OTC Medicines","Diagnostics","Home Delivery"],"certifications":[],"ratings":4.3,"benefit":"24/7 pharmacy. Part of Apollo chain. Diagnostic services available."},
    {"id":"p003","name":"Netmeds Pharmacy - Ghatlodia","type":"PHARMACY","category":"Retail Pharmacy","speciality":"Pharmacy","lat":23.034,"lng":72.543,"address":"Ghatlodia, Ahmedabad, Gujarat 380061","contact":"+91-79-27430555","emergency":False,"open24x7":False,"ayushmanCard":False,"maaCard":False,"cashlessCompanies":[],"services":["Prescription Medicines","OTC Medicines","Health Supplements"],"certifications":[],"ratings":4.0,"benefit":"Affordable generic medicines. Quick prescription processing."},
]


class MapService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.facilities = list(FACILITIES)
        # Try loading external JSON override
        json_path = Path(settings.BASE_DIR) / 'data' / 'location.json'
        if json_path.exists():
            try:
                with open(json_path) as f:
                    self.facilities = json.load(f)
                logger.info(f"Loaded {len(self.facilities)} locations from location.json")
            except Exception as e:
                logger.warning(f"Could not load location.json: {e}")

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)), 2)

    @staticmethod
    def eta(dist_km: float, speed=25) -> int:
        return max(1, round((dist_km / speed) * 60))

    @staticmethod
    def maps_link(lat, lng, name='') -> str:
        return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&destination_place_id={urllib.parse.quote(name)}"

    def _enrich(self, f: dict, ulat: float, ulng: float) -> dict:
        e = dict(f)
        d = self.haversine(ulat, ulng, f['lat'], f['lng'])
        e['distance'] = d
        e['estimatedTime'] = self.eta(d)
        e['googleMapsLink'] = self.maps_link(f['lat'], f['lng'], f['name'])
        return e

    def all_locations(self, ulat=None, ulng=None, category='ALL RESOURCES') -> list:
        result = list(self.facilities)
        if category and category.upper() != 'ALL RESOURCES':
            cl = category.lower()
            result = [f for f in result if (
                cl in f.get('type','').lower() or
                cl in f.get('speciality','').lower() or
                cl in f.get('category','').lower()
            )]
        if ulat is not None and ulng is not None:
            result = [self._enrich(f, ulat, ulng) for f in result]
            result.sort(key=lambda x: x.get('distance', 999))
        return result

    def nearby_hospitals(self, ulat, ulng, radius=20, speciality=None,
                         ayushman=False, maa=False, emergency=False) -> list:
        result = []
        for f in self.facilities:
            if f.get('type','').upper() != 'HOSPITAL':
                continue
            d = self.haversine(ulat, ulng, f['lat'], f['lng'])
            if d > radius:
                continue
            if speciality and speciality.lower() not in f.get('speciality','').lower():
                continue
            if ayushman and not f.get('ayushmanCard'):
                continue
            if maa and not f.get('maaCard'):
                continue
            if emergency and not f.get('emergency'):
                continue
            result.append(self._enrich(f, ulat, ulng))
        result.sort(key=lambda x: x.get('distance', 999))
        return result

    def nearby_pharmacies(self, ulat, ulng, radius=10, open_now=False) -> list:
        result = []
        for f in self.facilities:
            if f.get('type','').upper() != 'PHARMACY':
                continue
            d = self.haversine(ulat, ulng, f['lat'], f['lng'])
            if d > radius:
                continue
            if open_now and not f.get('open24x7'):
                continue
            result.append(self._enrich(f, ulat, ulng))
        result.sort(key=lambda x: x.get('distance', 999))
        return result

    def search(self, query: str, ftype=None) -> list:
        ql = query.lower()
        result = []
        for f in self.facilities:
            if ftype and f.get('type','').upper() != ftype.upper():
                continue
            blob = ' '.join([
                f.get('name',''), f.get('speciality',''), f.get('category',''),
                f.get('address',''), ' '.join(f.get('services',[])), f.get('benefit','')
            ]).lower()
            if ql in blob:
                result.append(dict(f))
        return result

    def by_id(self, fid: str):
        for f in self.facilities:
            if f.get('id') == fid:
                return dict(f)
        return None

    def emergency_hospitals(self, ulat=None, ulng=None) -> list:
        result = [dict(f) for f in self.facilities
                  if f.get('emergency') and f.get('type','').upper() == 'HOSPITAL']
        if ulat is not None and ulng is not None:
            result = [self._enrich(f, ulat, ulng) for f in result]
            result.sort(key=lambda x: x.get('distance', 999))
        return result


_map = None

def get_map():
    global _map
    if _map is None:
        _map = MapService()
    return _map
