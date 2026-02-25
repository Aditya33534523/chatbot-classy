"""
LIFEXIA RAG Service — Django Edition
Drug info from pharma.csv + Ollama LLM (Qwen2.5)
No hardcoded drug database — all answers come from CSV data or LLM tokens.
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


class RAGService:
    """
    Drug information service for Django LIFEXIA.
    Priority: pharma.csv → Qwen LLM (Ollama) → fallback message
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
        self.drug_db: dict = {}
        self.drug_aliases: dict = {}
        self.llm_available = False
        self._load_csv()
        self._load_llm()

    # ── CSV Loading ──────────────────────────────────────────────
    def _load_csv(self):
        csv_path = getattr(settings, 'PHARMA_CSV_PATH', '')
        if not csv_path or not Path(csv_path).exists():
            logger.info("pharma.csv not found — LLM-only mode")
            return
        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    key = row.get('generic_name', row.get('name', '')).strip().lower()
                    if not key or len(key) < 3:
                        continue
                    # Skip non-drug pharmacopoeia header rows
                    skip_keywords = ['properties and action', 'description', 'general', 'tests', 'apparatus',
                                     'monograph', 'tablets', 'injection', 'capsules', 'procedure', 'index',
                                     'abbreviations', 'department', 'volume', 'production', 'identification',
                                     'inhalation', 'oral', 'suppositories', 'dosage forms', 'introduction',
                                     'time mobile', 'chromatographic', 'name relative', 'code item']
                    if any(sk in key for sk in skip_keywords):
                        continue
                    uses_text = row.get('uses', row.get('use', '')).strip()
                    if not uses_text or len(uses_text) < 10:
                        continue

                    entry = {
                        "name": row.get('name', key.title()).strip(),
                        "generic": row.get('generic_name', key.title()).strip(),
                        "category": row.get('category', 'Pharmaceutical').strip(),
                        "use": uses_text,
                        "dosage": {
                            "adult": row.get('adult_dose', row.get('dosage', '')).strip() or 'Consult physician.',
                            "child": row.get('child_dose', '').strip() or 'Consult physician.',
                            "elderly": row.get('elderly_dose', '').strip() or 'Use caution, reduce dose.',
                        },
                        "side_effects": [s.strip() for s in row.get('side_effects', '').split(',') if s.strip()],
                        "contraindications": [s.strip() for s in row.get('contraindications', '').split(',') if s.strip()],
                        "interactions": [s.strip() for s in row.get('drug_interactions', row.get('interactions', '')).split(',') if s.strip()],
                        "warning": row.get('warnings', row.get('warning', '')).strip() or 'Consult your doctor.',
                        "emergency_use": row.get('emergency', 'false').lower() in ('true', '1', 'yes'),
                        "pharmacology": {
                            "mechanism": row.get('mechanism', '').strip(),
                            "half_life": row.get('half_life', '').strip(),
                            "metabolism": row.get('metabolism', '').strip(),
                            "excretion": row.get('excretion', '').strip(),
                        },
                    }
                    self.drug_db[key] = entry

                    brand = row.get('brand_names', row.get('brands', '')).strip()
                    for b in brand.split(','):
                        b = b.strip().lower()
                        if b and len(b) > 2:
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
                    logger.warning(f"Ollama model '{self.ollama_model}' not found. Available: {models}")
        except Exception as e:
            self.llm_available = False
            logger.warning(f"Ollama not available: {e} — CSV-only mode")

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

    def _extract_drug_from_question(self, question: str):
        patterns = [
            r"(?:about|info(?:rmation)?|details?|tell me about|what is|what's|explain)\s+(.+?)(?:\s*\?|$)",
            r"(?:dosage|dose|side effects?|uses?|interactions?|contraindications?)\s+(?:of|for)\s+(.+?)(?:\s*\?|$)",
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
            if len(w) > 3:
                d = self._find_drug(w)
                if d:
                    return d
        for i in range(len(words)):
            for j in range(i + 2, min(i + 5, len(words) + 1)):
                phrase = " ".join(words[i:j])
                d = self._find_drug(phrase)
                if d:
                    return d
        return None

    # ── Formatters ───────────────────────────────────────────────
    def _fmt_patient(self, drug: dict) -> str:
        d = drug.get('dosage', {})
        se = drug.get('side_effects', [])
        ci = drug.get('contraindications', [])
        interactions = drug.get('interactions', [])
        warning = drug.get('warning', '')
        use = drug.get('use', 'See prescribing information.')

        lines = []
        lines.append(f"## 💊 {drug['name']}")

        if drug.get('category'):
            lines.append(f"**{drug['category']}**")

        lines.append("")
        lines.append("### 🩺 What Is It Used For?")
        lines.append(use)

        # Dosage
        adult = d.get('adult', '').strip()
        child = d.get('child', '').strip()
        elderly = d.get('elderly', '').strip()

        if any([adult, child, elderly]):
            lines.append("")
            lines.append("### 💉 Dosage & Administration")
            if adult:
                lines.append(f"- **Adults:** {adult}")
            if child and child.lower() not in ('consult physician.', ''):
                lines.append(f"- **Children:** {child}")
            if elderly and elderly.lower() not in ('use caution, reduce dose.', ''):
                lines.append(f"- **Elderly:** {elderly}")

        # Warnings — prominent
        if warning:
            lines.append("")
            lines.append("### ⚠️ Important Warnings")
            lines.append(warning)

        # Side effects
        if se:
            lines.append("")
            lines.append("### 🔴 Side Effects")
            for s in se[:6]:
                lines.append(f"- {s}")

        # Contraindications
        if ci:
            lines.append("")
            lines.append("### 🚫 Do NOT Use If You Have")
            for c in ci[:5]:
                lines.append(f"- {c}")

        # Interactions
        if interactions:
            lines.append("")
            lines.append("### 🔄 Drug Interactions")
            for item in interactions[:5]:
                lines.append(f"- {item}")

        lines.append("")
        lines.append("---")
        lines.append("*⚕️ For reference only. Always consult your doctor or pharmacist before taking any medication.*")

        return "\n".join(lines)

    def _fmt_student(self, drug: dict) -> str:
        ph = drug.get('pharmacology', {})
        d = drug.get('dosage', {})
        se = drug.get('side_effects', [])
        ci = drug.get('contraindications', [])
        interactions = drug.get('interactions', [])

        lines = []
        lines.append(f"## 💊 {drug['name']}")

        meta_parts = []
        if drug.get('generic'):
            meta_parts.append(f"**Generic:** {drug['generic']}")
        if drug.get('category'):
            meta_parts.append(f"**Class:** {drug['category']}")
        if meta_parts:
            lines.append(" | ".join(meta_parts))

        lines.append("")
        lines.append("### 🩺 Clinical Uses")
        lines.append(drug.get('use', 'See prescribing information.'))

        # Dosage
        adult = d.get('adult', '').strip()
        child = d.get('child', '').strip()
        elderly = d.get('elderly', '').strip()

        if any([adult, child, elderly]):
            lines.append("")
            lines.append("### 💉 Dosage Guidelines")
            if adult:
                lines.append(f"- **Adults:** {adult}")
            if child and child.lower() not in ('consult physician.', ''):
                lines.append(f"- **Paediatric:** {child}")
            if elderly and elderly.lower() not in ('use caution, reduce dose.', ''):
                lines.append(f"- **Geriatric:** {elderly}")

        # Pharmacology table
        ph_rows = []
        if ph.get('mechanism'):
            ph_rows.append(('Mechanism of Action', ph['mechanism']))
        if ph.get('half_life'):
            ph_rows.append(('Half-life', ph['half_life']))
        if ph.get('metabolism'):
            ph_rows.append(('Metabolism', ph['metabolism']))
        if ph.get('excretion'):
            ph_rows.append(('Excretion', ph['excretion']))

        if ph_rows:
            lines.append("")
            lines.append("### 🔬 Pharmacokinetics")
            lines.append("| Parameter | Details |")
            lines.append("|-----------|---------|")
            for label, val in ph_rows:
                lines.append(f"| {label} | {val} |")

        if se:
            lines.append("")
            lines.append("### 🔴 Adverse Effects")
            for s in se:
                lines.append(f"- {s}")

        if ci:
            lines.append("")
            lines.append("### 🚫 Contraindications")
            for c in ci:
                lines.append(f"- {c}")

        if interactions:
            lines.append("")
            lines.append("### 🔄 Drug Interactions")
            for item in interactions:
                lines.append(f"- {item}")

        if drug.get('warning'):
            lines.append("")
            lines.append("### ⚠️ Clinical Warnings")
            lines.append(drug['warning'])

        lines.append("")
        lines.append("---")
        lines.append("*📚 Source: Indian Pharmacopoeia | WHO Essential Medicines List*")

        return "\n".join(lines)

    def format_drug(self, drug: dict, user_type: str = 'patient') -> str:
        if user_type == 'student':
            return self._fmt_student(drug)
        return self._fmt_patient(drug)

    # ── LLM Query (Ollama) ────────────────────────────────────────
    def _llm_query(self, question: str, user_type: str = 'patient') -> str:
        if not self.llm_available:
            return None

        # Build context from CSV if available
        csv_context = ""
        if self.drug_db:
            drug_names = ", ".join(list(self.drug_db.keys())[:30])
            csv_context = f"\nKnown drugs in database: {drug_names}\n"

        system_prompt = (
            "You are LIFEXIA, an expert AI pharmaceutical assistant. "
            "Always respond with detailed, well-structured medical information. "
            "Use rich markdown formatting:\n"
            "- Start with ## Drug Name as a heading\n"
            "- Use ### Section headings (e.g. ### 🩺 What Is It Used For?, ### 💉 Dosage, ### ⚠️ Warnings, ### 🔴 Side Effects, ### 🚫 Contraindications, ### 🔄 Drug Interactions)\n"
            "- Use bullet lists (- item) for lists of side effects, interactions, etc.\n"
            "- Use **bold** for important terms and dosage amounts\n"
            "- Use a markdown table with | Parameter | Details | columns for pharmacokinetics if relevant\n"
            "- End with a --- divider and an italic disclaimer\n"
            "Never invent or hallucinate drug data. If unsure, say so clearly. "
            f"{'Use simple, patient-friendly language.' if user_type == 'patient' else 'Use clinical pharmacological detail suitable for medical students and professionals.'}"
            f"{csv_context}"
        )

        try:
            payload = {
                "model": self.ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 600},
            }
            r = requests.post(
                f"{self.ollama_base}/api/chat",
                json=payload,
                timeout=90,
            )
            if r.status_code == 200:
                return r.json().get('message', {}).get('content', '').strip()
            logger.error(f"Ollama {r.status_code}: {r.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None

    # ── Main Query ───────────────────────────────────────────────
    def query(self, question: str, user_type: str = 'patient') -> str:
        ql = question.lower().strip()

        # Greetings
        if any(k in ql for k in ['hello', 'hi ', 'hey ', 'good morning', 'good afternoon', 'good evening']):
            return self._greeting()

        # Drug list request
        if any(k in ql for k in ['drug list', 'all drugs', 'available medicines', 'what drugs', 'list of drugs']):
            return self._drug_list()

        # Emergency list
        if any(k in ql for k in ['emergency drug', 'emergency list', 'emergency medication']):
            return self._emergency_list()

        # Step 1: Check CSV database
        drug = self._extract_drug_from_question(question)
        if drug:
            return self.format_drug(drug, user_type)

        # Step 2: Try LLM
        llm_resp = self._llm_query(question, user_type)
        if llm_resp:
            return llm_resp

        # Step 3: Helpful fallback
        return self._fallback(question)

    def _greeting(self) -> str:
        db_count = len(self.drug_db)
        db_note = f" I have **{db_count} drugs** loaded from the pharmacopoeia database." if db_count else ""
        llm_note = f" The **{self.ollama_model}** LLM is also available for broader questions." if self.llm_available else ""
        return (
            f"👋 Hello! Welcome to **LIFEXIA** — your AI pharmaceutical assistant.{db_note}{llm_note}\n\n"
            "**I can help you with:**\n"
            "- 💊 Drug information — dosages, uses, mechanism of action\n"
            "- ⚠️ Side effects & contraindications\n"
            "- 🔄 Drug interactions\n"
            "- 📋 Emergency drug reference\n\n"
            "**Try asking:** *\"Tell me about Amoxicillin\"* or *\"What are the side effects of Ciprofloxacin?\"*"
        )

    def _drug_list(self) -> str:
        if not self.drug_db:
            return "No drugs loaded from CSV yet. Please check your pharma.csv configuration."
        items = [f"- **{v['name']}** — {v.get('category', '')}" for v in list(self.drug_db.values())[:40]]
        return f"## 📋 Available Drug Database ({len(self.drug_db)} drugs)\n\n" + "\n".join(items) + "\n\n*Ask about any specific drug for full details.*"

    def _emergency_list(self) -> str:
        emergency = [v for v in self.drug_db.values() if v.get('emergency_use')]
        if not emergency:
            # Fall back to LLM
            llm_resp = self._llm_query("List the most important emergency drugs with brief uses", 'patient')
            if llm_resp:
                return "## 🚨 Emergency Drug Reference\n\n" + llm_resp
            return "🚨 **Emergency?** Call **108** immediately.\n\nFor emergency drug information, please consult a medical professional."

        r = "## 🚨 Emergency Drug Reference\n\n"
        for d in emergency:
            r += f"### 💊 {d['name']}\n- **Category:** {d.get('category')}\n- **Use:** {d.get('use', '')[:120]}\n\n"
        r += "\n📞 **Emergency:** Call **108** immediately."
        return r

    def _fallback(self, question: str) -> str:
        llm_status = "LLM is available for general questions." if self.llm_available else "LLM is offline."
        db_status = f"{len(self.drug_db)} drugs loaded from CSV." if self.drug_db else "No CSV database loaded."

        return (
            f"I couldn't find specific information for your query.\n\n"
            f"**System status:** {db_status} {llm_status}\n\n"
            "**For best results, try:**\n"
            "- *\"Tell me about [drug name]\"*\n"
            "- *\"Side effects of [drug name]\"*\n"
            "- *\"Dosage of [drug name] for adults\"*\n"
            "- *\"Drug interactions with [drug name]\"*\n\n"
            "🚨 **Medical Emergency?** Call **108** immediately."
        )

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