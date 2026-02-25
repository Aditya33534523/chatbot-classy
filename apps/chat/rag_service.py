"""
LIFEXIA RAG Service — Django Edition
Drug info from pharma.csv + built-in fallback DB + Qwen2.5-3B-Instruct LLM
"""

import os
import re
import csv
import json
import logging
import requests
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# BUILT-IN VERIFIED DRUG DATABASE (fallback when CSV not found)
# ══════════════════════════════════════════════════════════════════
DRUG_DATABASE = {
    "paracetamol": {
        "name": "Paracetamol (Acetaminophen)", "generic": "Paracetamol",
        "category": "Analgesic / Antipyretic",
        "use": "Pain relief and fever reduction.",
        "dosage": {"adult": "500mg–1000mg every 4–6h. Max 4g/day.", "child": "10–15 mg/kg every 4–6h.", "elderly": "Max 2–3g/day."},
        "side_effects": ["Nausea", "Rash (rare)", "Liver damage (overdose)"],
        "contraindications": ["Severe liver disease", "Chronic alcoholism"],
        "interactions": ["Warfarin", "Alcohol", "Carbamazepine"],
        "warning": "⚠️ Do not exceed 4g/day. Overdose causes fatal liver failure.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Inhibits COX in CNS", "half_life": "1–4h", "metabolism": "Hepatic", "excretion": "Renal"},
    },
    "aspirin": {
        "name": "Aspirin (Acetylsalicylic Acid)", "generic": "Aspirin",
        "category": "NSAID / Antiplatelet",
        "use": "Pain relief, fever, anti-inflammatory, heart attack/stroke prevention.",
        "dosage": {"adult": "Pain: 325–650mg every 4–6h. Cardiac: 75–100mg/day.", "child": "NOT for under 16 (Reye's syndrome).", "elderly": "Low-dose 75–100mg for cardiac protection."},
        "side_effects": ["GI bleeding", "Stomach ulcers", "Tinnitus"],
        "contraindications": ["Children under 16", "Active GI bleeding", "Last trimester pregnancy"],
        "interactions": ["Warfarin", "Methotrexate", "Ibuprofen"],
        "warning": "⚠️ Do NOT give to children with viral illness. Discontinue 7 days before surgery.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Irreversible COX-1/2 inhibitor", "half_life": "15–20 min", "metabolism": "Hepatic", "excretion": "Renal"},
    },
    "ibuprofen": {
        "name": "Ibuprofen", "generic": "Ibuprofen",
        "category": "NSAID",
        "use": "Pain, fever, inflammation. Headache, arthritis, menstrual cramps.",
        "dosage": {"adult": "200–400mg every 4–6h. Max 1200mg/day OTC.", "child": "5–10 mg/kg every 6–8h.", "elderly": "Use lowest effective dose."},
        "side_effects": ["GI upset", "Nausea", "Kidney impairment"],
        "contraindications": ["Active GI bleeding", "Severe renal impairment", "Third trimester pregnancy"],
        "interactions": ["Aspirin", "Warfarin", "ACE inhibitors"],
        "warning": "⚠️ Take with food. Increased cardiovascular risk at high doses.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Non-selective COX-1/2 inhibitor", "half_life": "2–4h", "metabolism": "Hepatic CYP2C9", "excretion": "Renal"},
    },
    "amoxicillin": {
        "name": "Amoxicillin", "generic": "Amoxicillin",
        "category": "Antibiotic (Penicillin)",
        "use": "Bacterial infections: respiratory, urinary tract, ear, dental, H. pylori.",
        "dosage": {"adult": "250–500mg every 8h for 5–14 days.", "child": "20–40 mg/kg/day in 3 doses.", "elderly": "Adjust for renal impairment."},
        "side_effects": ["Diarrhea", "Nausea", "Rash", "Yeast infections"],
        "contraindications": ["Penicillin allergy", "Infectious mononucleosis"],
        "interactions": ["Methotrexate", "Warfarin", "Oral contraceptives"],
        "warning": "⚠️ Complete full course. Stop if severe allergic reaction occurs.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Inhibits bacterial cell wall synthesis", "half_life": "1–1.5h", "metabolism": "Partially hepatic", "excretion": "Renal 60%"},
    },
    "metformin": {
        "name": "Metformin", "generic": "Metformin Hydrochloride",
        "category": "Antidiabetic (Biguanide)",
        "use": "Type 2 Diabetes first-line therapy. PCOS (off-label).",
        "dosage": {"adult": "Start 500mg once/twice daily with meals. Max 2000mg/day.", "child": "≥10 years: 500mg twice daily.", "elderly": "Start low, monitor renal function."},
        "side_effects": ["GI upset", "Metallic taste", "B12 deficiency (long-term)"],
        "contraindications": ["Severe renal impairment eGFR<30", "Before iodinated contrast"],
        "interactions": ["Alcohol", "Iodinated contrast", "Cimetidine"],
        "warning": "⚠️ Hold 48h before contrast procedures. Does NOT cause hypoglycaemia alone.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Reduces hepatic glucose output, increases insulin sensitivity", "half_life": "6.2h", "metabolism": "Not metabolised", "excretion": "Renal unchanged"},
    },
    "epinephrine": {
        "name": "Epinephrine (Adrenaline)", "generic": "Epinephrine",
        "category": "Emergency Sympathomimetic",
        "use": "Anaphylaxis (FIRST-LINE), cardiac arrest, severe asthma.",
        "dosage": {"adult": "Anaphylaxis: 0.3–0.5mg IM. Cardiac arrest: 1mg IV every 3–5 min.", "child": "0.01mg/kg IM max 0.3mg.", "elderly": "Standard emergency doses."},
        "side_effects": ["Tachycardia", "Anxiety", "Hypertension"],
        "contraindications": ["None absolute in life-threatening emergency"],
        "interactions": ["Beta-blockers", "MAO inhibitors", "TCAs"],
        "warning": "🚨 CRITICAL EMERGENCY DRUG. IM route for anaphylaxis. Call 108 immediately.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Alpha/Beta adrenergic agonist", "half_life": "2–3 min", "metabolism": "MAO/COMT", "excretion": "Renal"},
    },
    "salbutamol": {
        "name": "Salbutamol (Albuterol)", "generic": "Salbutamol Sulfate",
        "category": "Bronchodilator (SABA)",
        "use": "Acute asthma relief, bronchospasm, COPD.",
        "dosage": {"adult": "1–2 puffs (100–200mcg) every 4–6h. Severe: up to 10 puffs via spacer.", "child": "1–2 puffs as needed. Under 5: spacer with mask.", "elderly": "Standard adult doses."},
        "side_effects": ["Tremor", "Tachycardia", "Hypokalemia"],
        "contraindications": ["Known hypersensitivity (rare)"],
        "interactions": ["Beta-blockers", "Diuretics", "MAO inhibitors"],
        "warning": "⚠️ RESCUE INHALER ONLY. If using >3×/week, asthma is poorly controlled.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Selective Beta-2 agonist, bronchial smooth muscle relaxation", "half_life": "3–8h", "metabolism": "Hepatic", "excretion": "Renal"},
    },
    "diazepam": {
        "name": "Diazepam", "generic": "Diazepam",
        "category": "Benzodiazepine",
        "use": "Anxiety, seizures (status epilepticus), muscle spasm, alcohol withdrawal.",
        "dosage": {"adult": "Anxiety: 2–10mg 2–4×/day. Seizures: 5–10mg IV.", "child": "Seizures: 0.1–0.3 mg/kg IV.", "elderly": "2–2.5mg once/twice daily."},
        "side_effects": ["Sedation", "Dependence", "Respiratory depression"],
        "contraindications": ["Severe respiratory depression", "Myasthenia gravis", "Sleep apnoea"],
        "interactions": ["Alcohol", "Opioids (BLACK BOX)", "CNS depressants"],
        "warning": "⚠️ HIGH DEPENDENCE RISK. Never combine with alcohol/opioids. CONTROLLED SUBSTANCE.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Enhances GABA-A receptor activity", "half_life": "20–100h", "metabolism": "Hepatic CYP2C19/3A4", "excretion": "Renal"},
    },
    "insulin": {
        "name": "Insulin", "generic": "Insulin",
        "category": "Antidiabetic Hormone",
        "use": "Type 1 & 2 Diabetes, DKA, gestational diabetes.",
        "dosage": {"adult": "Individualized. Type 1: 0.4–1 unit/kg/day.", "child": "Individualized per glucose monitoring.", "elderly": "Start conservatively."},
        "side_effects": ["Hypoglycaemia", "Weight gain", "Injection site reactions"],
        "contraindications": ["Hypoglycaemia", "Known hypersensitivity"],
        "interactions": ["Oral hypoglycaemics", "Beta-blockers", "Alcohol"],
        "warning": "🚨 HYPOGLYCAEMIA RISK. Carry glucose tablets. Severe: seizures/unconsciousness.",
        "emergency_use": True,
        "pharmacology": {"mechanism": "Binds insulin receptors, facilitates glucose uptake", "half_life": "5–6 min plasma", "metabolism": "Hepatic/renal", "excretion": "Renal"},
    },
    "atorvastatin": {
        "name": "Atorvastatin", "generic": "Atorvastatin Calcium",
        "category": "Statin (HMG-CoA Reductase Inhibitor)",
        "use": "Hyperlipidaemia, cardiovascular risk reduction.",
        "dosage": {"adult": "10–20mg once daily evening. Max 80mg/day.", "child": "10–17 years: 10mg daily.", "elderly": "Standard dosing."},
        "side_effects": ["Muscle pain", "Elevated liver enzymes", "Rhabdomyolysis (rare)"],
        "contraindications": ["Active liver disease", "Pregnancy"],
        "interactions": ["Gemfibrozil", "Grapefruit juice", "Warfarin"],
        "warning": "⚠️ Report unexplained muscle pain. Contraindicated in pregnancy.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Competitive HMG-CoA reductase inhibitor", "half_life": "14h", "metabolism": "Hepatic CYP3A4", "excretion": "Biliary"},
    },
    "omeprazole": {
        "name": "Omeprazole", "generic": "Omeprazole",
        "category": "Proton Pump Inhibitor",
        "use": "GERD, peptic ulcers, H. pylori eradication, NSAID-induced ulcer prevention.",
        "dosage": {"adult": "20mg once daily before breakfast.", "child": "1 mg/kg once daily max 20mg.", "elderly": "No adjustment usually."},
        "side_effects": ["Headache", "Diarrhea", "B12 deficiency (long-term)"],
        "contraindications": ["Known PPI hypersensitivity", "Concurrent rilpivirine"],
        "interactions": ["Clopidogrel (AVOID)", "Warfarin", "Methotrexate"],
        "warning": "⚠️ Not for long-term use without review. Risk of C. difficile infection.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Irreversible H+/K+ ATPase inhibitor", "half_life": "0.5–1h", "metabolism": "Hepatic CYP2C19/3A4", "excretion": "Renal 77%"},
    },
    "cetirizine": {
        "name": "Cetirizine", "generic": "Cetirizine Hydrochloride",
        "category": "Antihistamine (2nd generation)",
        "use": "Allergic rhinitis, urticaria, hay fever, skin allergies.",
        "dosage": {"adult": "10mg once daily.", "child": "2–5 years: 2.5mg. 6–11 years: 5–10mg.", "elderly": "5mg daily."},
        "side_effects": ["Drowsiness (mild)", "Dry mouth", "Headache"],
        "contraindications": ["Severe renal impairment without adjustment"],
        "interactions": ["Alcohol", "CNS depressants"],
        "warning": "⚠️ May cause drowsiness. Avoid driving if affected.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Selective H1 receptor antagonist", "half_life": "8h", "metabolism": "Minimal hepatic", "excretion": "Renal 70%"},
    },
    "amlodipine": {
        "name": "Amlodipine", "generic": "Amlodipine Besylate",
        "category": "Calcium Channel Blocker",
        "use": "Hypertension, chronic stable angina.",
        "dosage": {"adult": "5mg once daily. May increase to 10mg.", "child": "6–17 years: 2.5–5mg once daily.", "elderly": "Start 2.5mg."},
        "side_effects": ["Ankle swelling", "Headache", "Flushing"],
        "contraindications": ["Cardiogenic shock", "Severe aortic stenosis"],
        "interactions": ["Simvastatin (limit 20mg)", "CYP3A4 inhibitors"],
        "warning": "⚠️ Do not stop abruptly in angina. Monitor blood pressure regularly.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Blocks L-type calcium channels, vasodilation", "half_life": "30–50h", "metabolism": "Hepatic CYP3A4", "excretion": "Renal 60%"},
    },
    "ciprofloxacin": {
        "name": "Ciprofloxacin", "generic": "Ciprofloxacin Hydrochloride",
        "category": "Antibiotic (Fluoroquinolone)",
        "use": "UTI, respiratory, GI, bone/joint infections.",
        "dosage": {"adult": "250–750mg twice daily 3–14 days.", "child": "Not recommended under 18 except anthrax/complicated UTI.", "elderly": "Adjust for renal impairment."},
        "side_effects": ["Nausea", "Tendon rupture", "Photosensitivity", "QT prolongation"],
        "contraindications": ["Children/adolescents", "History of fluoroquinolone tendon disorders"],
        "interactions": ["Antacids/iron (take 2h apart)", "Warfarin", "Theophylline"],
        "warning": "⚠️ BLACK BOX: Tendinitis, tendon rupture, neuropathy risk.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Inhibits DNA gyrase and topoisomerase IV", "half_life": "4–6h", "metabolism": "Partial hepatic", "excretion": "Renal 40–50%"},
    },
    "losartan": {
        "name": "Losartan", "generic": "Losartan Potassium",
        "category": "ARB (Angiotensin II Receptor Blocker)",
        "use": "Hypertension, diabetic nephropathy, stroke risk reduction.",
        "dosage": {"adult": "50mg once daily. May increase to 100mg.", "child": "6–16 years: 0.7 mg/kg once daily.", "elderly": "Start conservatively."},
        "side_effects": ["Dizziness", "Hyperkalemia", "Hypotension"],
        "contraindications": ["Pregnancy (TERATOGENIC)", "Bilateral renal artery stenosis"],
        "interactions": ["Potassium supplements", "NSAIDs", "ACE inhibitors"],
        "warning": "⚠️ CONTRAINDICATED IN PREGNANCY. Discontinue immediately if pregnant.",
        "emergency_use": False,
        "pharmacology": {"mechanism": "Selective AT1 receptor antagonist", "half_life": "2h (losartan) / 6–9h (active metabolite)", "metabolism": "Hepatic CYP2C9/3A4", "excretion": "Renal 35% + Biliary 60%"},
    },
}

DRUG_ALIASES = {
    "acetaminophen": "paracetamol", "tylenol": "paracetamol",
    "crocin": "paracetamol", "dolo": "paracetamol", "dolo 650": "paracetamol",
    "calpol": "paracetamol", "disprin": "aspirin", "ecosprin": "aspirin",
    "brufen": "ibuprofen", "advil": "ibuprofen", "combiflam": "ibuprofen",
    "augmentin": "amoxicillin", "mox": "amoxicillin",
    "glycomet": "metformin", "glucophage": "metformin",
    "adrenaline": "epinephrine", "epipen": "epinephrine",
    "asthalin": "salbutamol", "ventolin": "salbutamol", "albuterol": "salbutamol",
    "valium": "diazepam", "calmpose": "diazepam",
    "humulin": "insulin", "lantus": "insulin", "novorapid": "insulin",
    "lipitor": "atorvastatin", "atorva": "atorvastatin",
    "omez": "omeprazole", "prilosec": "omeprazole",
    "zyrtec": "cetirizine", "alerid": "cetirizine",
    "stamlo": "amlodipine", "norvasc": "amlodipine",
    "ciplox": "ciprofloxacin", "cipro": "ciprofloxacin",
    "repace": "losartan", "cozaar": "losartan",
}


class RAGService:
    """
    Drug information service for Django LIFEXIA.
    Priority: pharma.csv → built-in DB → Qwen LLM
    """
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
        self.drug_db = dict(DRUG_DATABASE)
        self.drug_aliases = dict(DRUG_ALIASES)
        self.llm_available = False
        self._load_csv()
        self._load_llm()

    # ── CSV Loading ──────────────────────────────────────────────
    def _load_csv(self):
        csv_path = getattr(settings, 'PHARMA_CSV_PATH', '')
        if not csv_path or not Path(csv_path).exists():
            logger.info("pharma.csv not found — using built-in drug DB")
            return
        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    key = row.get('generic_name', row.get('name', '')).strip().lower()
                    if not key:
                        continue
                    entry = {
                        "name": row.get('name', key.title()),
                        "generic": row.get('generic_name', key.title()),
                        "category": row.get('category', 'Pharmaceutical'),
                        "use": row.get('uses', row.get('use', 'See prescribing information.')),
                        "dosage": {
                            "adult": row.get('adult_dose', row.get('dosage', 'Consult physician.')),
                            "child": row.get('child_dose', 'Consult physician.'),
                            "elderly": row.get('elderly_dose', 'Use caution, reduce dose.'),
                        },
                        "side_effects": [s.strip() for s in row.get('side_effects', '').split(',') if s.strip()],
                        "contraindications": [s.strip() for s in row.get('contraindications', '').split(',') if s.strip()],
                        "interactions": [s.strip() for s in row.get('drug_interactions', row.get('interactions', '')).split(',') if s.strip()],
                        "warning": row.get('warnings', row.get('warning', 'Consult your doctor.')),
                        "emergency_use": row.get('emergency', 'false').lower() in ('true', '1', 'yes'),
                        "pharmacology": {
                            "mechanism": row.get('mechanism', ''),
                            "half_life": row.get('half_life', ''),
                            "metabolism": row.get('metabolism', ''),
                            "excretion": row.get('excretion', ''),
                        },
                        "_from_csv": True,
                    }
                    self.drug_db[key] = entry
                    # Register brand names / aliases from CSV
                    brand = row.get('brand_names', row.get('brands', ''))
                    for b in brand.split(','):
                        b = b.strip().lower()
                        if b:
                            self.drug_aliases[b] = key
                    count += 1
            logger.info(f"Loaded {count} drugs from pharma.csv")
        except Exception as e:
            logger.error(f"CSV load error: {e}")

    # ── Ollama LLM Setup ─────────────────────────────────────────
    def _load_llm(self):
        self.ollama_base = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        self.ollama_model = getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:3b')
        try:
            r = requests.get(f"{self.ollama_base}/api/tags", timeout=3)
            if r.status_code == 200:
                models = [m['name'] for m in r.json().get('models', [])]
                if any(self.ollama_model in m for m in models):
                    self.llm_available = True
                    logger.info(f"Ollama connected — model '{self.ollama_model}' ready")
                else:
                    self.llm_available = False
                    logger.warning(f"Ollama running but model '{self.ollama_model}' not found. Available: {models}")
            else:
                self.llm_available = False
                logger.warning("Ollama not responding — DB-only mode")
        except Exception as e:
            self.llm_available = False
            logger.warning(f"Ollama connection failed: {e} — DB-only mode")

    # ── Drug Lookup ──────────────────────────────────────────────
    def _find_drug(self, query: str):
        q = query.lower().strip()
        if q in self.drug_db:
            return self.drug_db[q]
        if q in self.drug_aliases:
            return self.drug_db.get(self.drug_aliases[q])
        for k, v in self.drug_db.items():
            if k in q or q in k:
                return v
            if q in v.get('name', '').lower() or q in v.get('generic', '').lower():
                return v
        for alias, target in self.drug_aliases.items():
            if alias in q or q in alias:
                return self.drug_db.get(target)
        return None

    def _extract_drug(self, question: str):
        patterns = [
            r"(?:about|info(?:rmation)?|details?|tell me about|what is|what's)\s+(.+?)(?:\s*\?|$)",
            r"(?:dosage|dose|side effects?|uses?|interactions?)\s+(?:of|for)\s+(.+?)(?:\s*\?|$)",
            r"(?:how to (?:use|take))\s+(.+?)(?:\s*\?|$)",
        ]
        for pat in patterns:
            m = re.search(pat, question, re.IGNORECASE)
            if m:
                d = self._find_drug(m.group(1).strip())
                if d:
                    return d
        words = question.split()
        for w in words:
            d = self._find_drug(w)
            if d:
                return d
        for i in range(len(words)):
            for j in range(i + 2, min(i + 5, len(words) + 1)):
                d = self._find_drug(" ".join(words[i:j]))
                if d:
                    return d
        return None

    # ── Formatters ───────────────────────────────────────────────
    def _fmt_patient(self, drug: dict) -> str:
        se = ", ".join(drug.get('side_effects', [])[:5]) or "Mild and generally well-tolerated"
        ci = ", ".join(drug.get('contraindications', [])[:3]) or "None significant"
        interactions = ", ".join(drug.get('interactions', [])[:4]) or "None significant"
        d = drug.get('dosage', {})
        return f"""## 💊 {drug['name']}
**Category:** {drug.get('category', 'N/A')}

### What is it used for?
{drug.get('use', 'N/A')}

### 📋 Dosage
- **Adults:** {d.get('adult', 'Consult physician')}
- **Children:** {d.get('child', 'Consult physician')}

### ⚠️ Warnings
{drug.get('warning', 'Consult your doctor before use.')}

### Side Effects
{se}

### Do NOT Use If
{ci}

### Drug Interactions
{interactions}

---
*⚕️ For reference only. Always consult your doctor or pharmacist.*"""

    def _fmt_student(self, drug: dict) -> str:
        ph = drug.get('pharmacology', {})
        d = drug.get('dosage', {})
        return f"""## 💊 {drug['name']}
**Generic:** {drug.get('generic', 'N/A')} | **Category:** {drug.get('category', 'N/A')}

### Clinical Uses
{drug.get('use', 'N/A')}

### Dosage Guidelines
- **Adults:** {d.get('adult', 'N/A')}
- **Paediatric:** {d.get('child', 'N/A')}
- **Geriatric:** {d.get('elderly', 'N/A')}

### Pharmacology
| Parameter | Details |
|-----------|---------|
| **Mechanism** | {ph.get('mechanism', 'N/A')} |
| **Half-life** | {ph.get('half_life', 'N/A')} |
| **Metabolism** | {ph.get('metabolism', 'N/A')} |
| **Excretion** | {ph.get('excretion', 'N/A')} |

### Side Effects
{chr(10).join(['- ' + s for s in drug.get('side_effects', [])])}

### Contraindications
{chr(10).join(['- ' + c for c in drug.get('contraindications', [])])}

### Drug Interactions
{chr(10).join(['- ' + i for i in drug.get('interactions', [])])}

### ⚠️ Warnings
{drug.get('warning', 'N/A')}

---
*📚 Source: Indian Pharmacopoeia 2022 | NLEM 2022 | WHO Essential Medicines*"""

    def format_drug(self, drug: dict, user_type: str = 'patient') -> str:
        if user_type == 'student':
            return self._fmt_student(drug)
        return self._fmt_patient(drug)

    # ── LLM Query (Ollama) ────────────────────────────────────────
    def _llm_query(self, question: str) -> str:
        if not self.llm_available:
            return None
        try:
            payload = {
                "model": self.ollama_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are LIFEXIA, an AI pharmaceutical assistant. "
                            "Provide accurate, helpful drug information. "
                            "If you don't know something, say so clearly. "
                            "Never invent drug information. Keep answers concise."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 300},
            }
            r = requests.post(
                f"{self.ollama_base}/api/chat",
                json=payload,
                timeout=60,
            )
            if r.status_code == 200:
                return r.json().get('message', {}).get('content', '').strip()
            logger.error(f"Ollama returned {r.status_code}: {r.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Ollama query error: {e}")
            return None

    # ── Main Query ───────────────────────────────────────────────
    def query(self, question: str, user_type: str = 'patient') -> str:
        # Step 1: Check drug database first (no hallucination)
        drug = self._extract_drug(question)
        if drug:
            return self.format_drug(drug, user_type)

        ql = question.lower()

        # Step 2: Handle common intents
        if any(k in ql for k in ['emergency drug', 'emergency list', 'emergency medication']):
            items = [d for d in self.drug_db.values() if d.get('emergency_use')]
            r = "## 🚨 Emergency Drug Reference\n\n"
            for d in items:
                r += f"### 💊 {d['name']}\n- **Category:** {d.get('category')}\n- **Use:** {d.get('use', '')[:100]}...\n\n"
            return r

        if any(k in ql for k in ['drug list', 'all drugs', 'available medicines', 'what drugs']):
            items = [f"- **{v['name']}** — {v.get('category', '')}" for v in self.drug_db.values()]
            return f"## 📋 Available Drug Database\n\n" + "\n".join(items) + "\n\n*Ask about any specific drug for full details.*"

        if any(k in ql for k in ['hello', 'hi ', 'hey', 'good morning', 'good afternoon']):
            return """👋 Hello! Welcome to **LIFEXIA** — your AI pharmaceutical assistant.

**I can help you with:**
- 💊 Drug information — dosages, uses, mechanism of action
- ⚠️ Side effects & contraindications
- 🔄 Drug interactions
- 📋 Emergency drug reference
- 🏥 Patient & student modes

**Try asking:** *"Tell me about Paracetamol"* or *"Dosage of Amoxicillin for a child"*"""

        # Step 3: Try LLM
        llm_resp = self._llm_query(question)
        if llm_resp:
            return llm_resp

        # Step 4: Helpful fallback
        drugs_list = ", ".join([v['name'] for v in list(self.drug_db.values())[:10]])
        return f"""I have verified information for: **{drugs_list}** and more.

For the best results, try:
- *"Tell me about [drug name]"*
- *"Side effects of [drug name]"*
- *"Dosage for [drug name]"*
- *"Emergency drugs list"*

🚨 **Emergency?** Call **108** immediately."""

    # ── Utility ──────────────────────────────────────────────────
    def search_drug(self, name: str):
        return self._find_drug(name)

    def emergency_drugs(self):
        return [v for v in self.drug_db.values() if v.get('emergency_use')]

    def all_categories(self):
        return list(set(v.get('category', '') for v in self.drug_db.values()))


# Singleton accessor
_rag = None

def get_rag():
    global _rag
    if _rag is None:
        _rag = RAGService()
    return _rag
