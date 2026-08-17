"""
AI service for incident summarization and log queries.
Uses Google Vertex AI/Gemini for LLM capabilities.
"""
import json
import os
from typing import Any, Optional

try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("⚠️  Vertex AI not available. Install: pip install google-cloud-aiplatform vertexai")


def get_vertex_ai_client():
    """Initialize Vertex AI client."""
    if not VERTEX_AI_AVAILABLE:
        print("⚠️  Vertex AI not installed. Using fallback mode.")
        return None

    # Get project ID from environment or use default
    project_id = os.getenv("GCP_PROJECT_ID", "resume-agent-484309")
    location = os.getenv("GCP_LOCATION", "us-central1")

    try:
        # Try to initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        model = GenerativeModel("gemini-1.5-flash")
        # Test with a simple call to verify auth works
        return model
    except Exception as e:
        print(f"⚠️  Vertex AI initialization failed: {e}")
        if "authentication" in str(e).lower() or "credentials" in str(e).lower():
            print("   💡 Authentication issue. Options:")
            print("      1. Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
            print("      2. Run: gcloud auth application-default login")
            print("      3. Continue without AI (fallback mode)")
        else:
            print("   Using fallback mode (basic responses)")
        return None


def summarize_incident(
    logs: list[dict[str, Any]],
    service: Optional[str] = None,
    time_window: str = "",
) -> dict[str, Optional[str]]:
    """
    Summarize an incident using AI.

    Returns:
        {
            "summary": "What happened",
            "root_cause": "Likely cause",
            "next_steps": "Recommended actions"
        }
    """
    if not logs:
        return {
            "summary": "No logs available for analysis.",
            "root_cause": None,
            "next_steps": "Check if logs are being ingested correctly.",
        }

    try:
        model = get_vertex_ai_client()
        if model is None:
            # Fallback: generate basic summary without LLM
            return _generate_fallback_summary(logs, service)

        # Sample and deduplicate logs
        unique_logs = _deduplicate_logs(logs)
        sample_logs = unique_logs[:40]  # Top 40 unique examples

        # Build prompt
        prompt = _build_summarization_prompt(sample_logs, service, time_window)

        # Call LLM
        response = model.generate_content(prompt)
        result_text = response.text

        # Parse structured response
        return _parse_llm_response(result_text)

    except Exception as e:
        print(f"❌ AI summarization error: {e}")
        return _generate_fallback_summary(logs, service)


def _deduplicate_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate logs by message content."""
    seen = set()
    unique = []
    for log in logs:
        message = log.get("message", "")
        if message not in seen:
            seen.add(message)
            unique.append(log)
    return unique


def _build_summarization_prompt(
    logs: list[dict[str, Any]],
    service: Optional[str],
    time_window: str,
) -> str:
    """Build prompt for incident summarization."""
    log_examples = "\n".join([
        f"- [{log.get('timestamp', '')}] {log.get('level', '')} {log.get('service', '')}: {log.get('message', '')}"
        for log in logs[:40]
    ])

    service_context = f"Service: {service}\n" if service else "All services\n"

    return f"""You are an incident response analyst. Analyze these log entries and provide a structured summary.

{service_context}Time Window: {time_window}
Total Logs: {len(logs)}

Log Entries:
{log_examples}

Provide your analysis in this exact JSON format:
{{
  "summary": "2-4 sentences describing what happened",
  "root_cause": "Hypothesis about the likely root cause (1-2 sentences)",
  "next_steps": "3-6 bullet points with recommended next steps"
}}

Be concise, technical, and actionable. Focus on patterns and anomalies."""


def _parse_llm_response(text: str) -> dict[str, Optional[str]]:
    """Parse LLM response into structured format."""
    try:
        # Try to extract JSON from response
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            json_str = text[start:end]
            parsed = json.loads(json_str)
            return {
                "summary": parsed.get("summary", ""),
                "root_cause": parsed.get("root_cause"),
                "next_steps": parsed.get("next_steps"),
            }
    except Exception:
        pass

    # Fallback: return as summary
    return {
        "summary": text[:500],  # Truncate if too long
        "root_cause": None,
        "next_steps": None,
    }


def _generate_fallback_summary(
    logs: list[dict[str, Any]],
    service: Optional[str],
) -> dict[str, Optional[str]]:
    """Generate summary without LLM (fallback)."""
    error_count = sum(1 for log in logs if log.get("level") in ["ERROR", "FATAL"])
    warn_count = sum(1 for log in logs if log.get("level") == "WARN")

    services = set(log.get("service", "unknown") for log in logs)
    service_list = ", ".join(list(services)[:3])

    summary = f"Detected {len(logs)} log entries"
    if service:
        summary += f" from {service}"
    else:
        summary += f" across {len(services)} service(s): {service_list}"
    summary += f". {error_count} errors and {warn_count} warnings."

    root_cause = "Review log patterns and error messages above for common themes."

    next_steps = """• Check service health metrics
• Review recent deployments
• Examine related error logs
• Verify dependencies are healthy"""

    return {
        "summary": summary,
        "root_cause": root_cause,
        "next_steps": next_steps,
    }


def answer_log_question(
    question: str,
    logs: list[dict[str, Any]],
    context: Optional[str] = None,
) -> dict[str, Any]:
    """
    Answer a question about logs using RAG.

    Returns:
        {
            "answer": "Answer text",
            "citations": [{"log_id": "...", "timestamp": "...", "message": "..."}]
        }
    """
    if not logs:
        return {
            "answer": "No logs found matching your query. Try adjusting your filters or time range.",
            "citations": [],
        }

    try:
        model = get_vertex_ai_client()
        if model is None:
            return _generate_fallback_answer(question, logs)

        # Build prompt with log context
        prompt = _build_question_prompt(question, logs, context)

        # Call LLM
        response = model.generate_content(prompt)
        answer = response.text

        # Extract citations (log IDs mentioned in answer or top relevant logs)
        citations = _extract_citations(logs, answer)

        return {
            "answer": answer,
            "citations": citations,
        }

    except Exception as e:
        print(f"❌ AI question answering error: {e}")
        return _generate_fallback_answer(question, logs)


def _build_question_prompt(
    question: str,
    logs: list[dict[str, Any]],
    context: Optional[str],
) -> str:
    """Build prompt for log question answering."""
    log_context = "\n".join([
        f"[ID: {log.get('id', 'N/A')}] {log.get('timestamp', '')} | {log.get('level', '')} | {log.get('service', '')}: {log.get('message', '')}"
        for log in logs[:50]  # Top 50 logs
    ])

    context_str = f"\nAdditional Context: {context}\n" if context else ""

    return f"""You are a log analysis assistant. Answer the user's question based ONLY on the provided log entries.

{context_str}
Log Entries:
{log_context}

User Question: {question}

Instructions:
- Answer based ONLY on the logs provided above
- Cite specific log IDs when referencing logs (format: [ID: xxx])
- Be concise and factual
- If the answer isn't in the logs, say so
- Format your answer clearly with bullet points if needed

Answer:"""


def _extract_citations(
    logs: list[dict[str, Any]],
    answer: str,
) -> list[dict[str, str]]:
    """Extract log citations from answer or return top relevant logs."""
    citations = []

    # Try to find log IDs mentioned in answer
    import re
    id_matches = re.findall(r'\[ID:\s*([^\]]+)\]', answer)

    # Build citation list from mentioned IDs or top logs
    cited_ids = set(id_matches[:10])  # Limit to 10 citations

    for log in logs[:20]:  # Check top 20 logs
        log_id = str(log.get("id", ""))
        if log_id in cited_ids or len(citations) < 5:
            citations.append({
                "log_id": log_id,
                "timestamp": str(log.get("timestamp", "")),
                "service": log.get("service", ""),
                "level": log.get("level", ""),
                "message": log.get("message", "")[:200],  # Truncate long messages
            })
            if len(citations) >= 10:
                break

    return citations


def _generate_fallback_answer(question: str, logs: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate answer without LLM (fallback)."""
    error_logs = [log for log in logs if log.get("level") in ["ERROR", "FATAL"]]

    if "error" in question.lower() or "fail" in question.lower():
        answer = f"Found {len(error_logs)} error logs. "
        if error_logs:
            top_error = error_logs[0]
            answer += f"Most recent: {top_error.get('message', '')[:200]}"
    else:
        answer = f"Found {len(logs)} matching logs. "
        if logs:
            answer += f"Most recent entry: {logs[0].get('message', '')[:200]}"

    citations = [
        {
            "log_id": str(log.get("id", "")),
            "timestamp": str(log.get("timestamp", "")),
            "service": log.get("service", ""),
            "level": log.get("level", ""),
            "message": log.get("message", "")[:200],
        }
        for log in logs[:5]
    ]

    return {
        "answer": answer,
        "citations": citations,
    }
