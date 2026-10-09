import os
import json
import re
from typing import Optional, Dict, Any, List
from backend.config import settings

class LLMClient:
    """
    Unified LLM provider abstraction supporting Google Gemini, OpenAI,
    and a deterministic Local Intelligence Engine fallback when no API key is provided.
    """

    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or settings.GEMINI_API_KEY
        self.openai_key = os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        
        self.active_provider = "local"
        if settings.LLM_PROVIDER == "gemini" and self.gemini_key:
            self.active_provider = "gemini"
        elif settings.LLM_PROVIDER == "openai" and self.openai_key:
            self.active_provider = "openai"
        elif settings.LLM_PROVIDER == "auto":
            if self.gemini_key:
                self.active_provider = "gemini"
            elif self.openai_key:
                self.active_provider = "openai"
            else:
                self.active_provider = "local"

    def is_cloud_enabled(self) -> bool:
        return self.active_provider in ["gemini", "openai"]

    def get_provider_name(self) -> str:
        if self.active_provider == "gemini":
            return f"Google Gemini ({settings.GEMINI_MODEL})"
        elif self.active_provider == "openai":
            return f"OpenAI ({settings.OPENAI_MODEL})"
        return "Deterministic Procurement Engine (Local/Offline)"

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        if self.active_provider == "gemini":
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    google_api_key=self.gemini_key,
                    temperature=temperature
                )
                messages = []
                if system_prompt:
                    messages.append(("system", system_prompt))
                messages.append(("human", prompt))
                resp = llm.invoke(messages)
                return str(resp.content)
            except Exception as e:
                # Fall back to local engine if cloud call fails
                print(f"[LLMClient] Gemini call error: {e}. Falling back to local engine.")
                return self._local_generate(prompt, system_prompt)

        elif self.active_provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=self.openai_key,
                    temperature=temperature
                )
                messages = []
                if system_prompt:
                    messages.append(("system", system_prompt))
                messages.append(("human", prompt))
                resp = llm.invoke(messages)
                return str(resp.content)
            except Exception as e:
                print(f"[LLMClient] OpenAI call error: {e}. Falling back to local engine.")
                return self._local_generate(prompt, system_prompt)

        return self._local_generate(prompt, system_prompt)

    def extract_json(self, prompt: str, system_prompt: str = "") -> Any:
        response_text = self.generate(prompt, system_prompt)
        
        # Strip markdown json code fences if present
        clean = response_text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(clean)
        except Exception:
            # Try regex to locate first JSON array or object
            json_match = re.search(r'(\[.*\]|\{.*\})', clean, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except Exception:
                    pass
            return {"raw_response": response_text}

    def _local_generate(self, prompt: str, system_prompt: str) -> str:
        """
        Local deterministic generator that synthesizes answers from evidence passages
        and respects guardrails when no API key is provided.
        """
        # Look for question in prompt
        q_match = re.search(r'(?:Question|Query):\s*(.*?)(?:\n|$)', prompt, re.I)
        question = q_match.group(1).strip() if q_match else prompt

        # Extract context chunks from prompt
        context_matches = re.findall(r'\[Page\s*(\d+)\](?:\s*\[Chunk\s*([^\]]+)\])?\s*(.*?)(?=\n\[Page|\n---|\Z)', prompt, re.DOTALL)
        
        if not context_matches:
            return "Based on the tender documents reviewed, insufficient evidence was found in the text to verify this requirement or claim."

        # Scan context for best matching passage to the question keywords
        q_tokens = set(re.findall(r'[a-zA-Z0-9]+', question.lower())) - {"what", "is", "the", "are", "for", "in", "and", "of", "to", "a"}
        
        best_page = 1
        best_passage = ""
        best_overlap = -1

        for page_num, chunk_id, passage in context_matches:
            passage_tokens = set(re.findall(r'[a-zA-Z0-9]+', passage.lower()))
            overlap = len(q_tokens & passage_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_page = int(page_num)
                best_passage = passage.strip()

        if best_overlap <= 0:
            return "No direct evidence found in the provided tender sections matching your specific inquiry. Final verification should be confirmed with the tendering authority."

        # Extract the key sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', best_passage) if s.strip()]
        relevant_sentences = []
        for s in sentences:
            s_tokens = set(re.findall(r'[a-zA-Z0-9]+', s.lower()))
            if len(s_tokens & q_tokens) > 0:
                relevant_sentences.append(s)

        summary_text = " ".join(relevant_sentences[:3]) if relevant_sentences else best_passage[:250]
        return f"{summary_text} (Source: Page {best_page})"

llm_client = LLMClient()
