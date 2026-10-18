"""
HTTP client for the CyberLibrarian API with a built-in mock mode.

USE_MOCK=true  (the default) → returns a hardcoded AnswerResponse built from
               real OWASP and NIST text so the UI works before the API is running.
USE_MOCK=false → POSTs to API_URL/ask and parses the response.

Switching between mock and real requires changing only the USE_MOCK env var.
"""
from __future__ import annotations

import requests

from src.common.config import Config
from src.common.schemas import AnswerResponse, Citation, Chunk, RetrievalResult

# ---------------------------------------------------------------------------
# Hardcoded mock chunks – taken verbatim from real OWASP / NIST source text
# so that the mock demonstrates what a real answer looks like.
# ---------------------------------------------------------------------------

_MOCK_CHUNK_1 = Chunk(
    chunk_id="owasp-sql-injection-prevention-cheat-sheet-0",
    doc_id="owasp-sql-injection-prevention-cheat-sheet",
    title="SQL Injection Prevention Cheat Sheet",
    source="owasp",
    section="SQL Injection Prevention",
    date=None,
    position=0,
    text=(
        "The use of prepared statements (also known as parameterized queries) is "
        "the primary defense against SQL injection. Prepared statements ensure "
        "that an attacker is not able to change the intent of a query, even if "
        "SQL commands are inserted. In the safe example below, if an attacker were "
        "to enter userID of 'tom' OR '1'='1', the parameterized query would not be "
        "vulnerable and would instead look for a username that literally matched "
        "the entire string 'tom' OR '1'='1'."
    ),
)

_MOCK_CHUNK_2 = Chunk(
    chunk_id="nist-sp800-61r3-p1",
    doc_id="nist-sp800-61r3-p1",
    title="SP 800-61 Rev 3: Computer Security Incident Handling Guide",
    source="nist",
    section="Page 1",
    date="2024-08-23",
    position=0,
    text=(
        "An incident is defined as a violation or imminent threat of violation of "
        "computer security policies, acceptable use policies, or standard security "
        "practices. Examples of incidents are: an attacker commanding a botnet to "
        "send high volumes of connection requests to a web server, causing it to "
        "crash; a user providing or disclosing sensitive information to others "
        "through phishing; a user downloading software that contains malicious "
        "code; an attacker obtaining sensitive data and threatening to release it "
        "publicly if the organization does not pay a ransom."
    ),
)

_MOCK_CHUNK_3 = Chunk(
    chunk_id="mitre-T1059-0",
    doc_id="mitre-T1059",
    title="Command and Scripting Interpreter (T1059)",
    source="mitre",
    section="execution",
    date="2023-10-04",
    position=0,
    text=(
        "Adversaries may abuse command and script interpreters to execute commands, "
        "scripts, or binaries. These interfaces and languages provide ways of "
        "interacting with computer systems and are a common feature across many "
        "different platforms. Most systems come with some built-in command-line "
        "interface and scripting capabilities, for example, macOS and Linux "
        "distributions include some flavor of Unix Shell while Windows installations "
        "include the Windows Command Shell and PowerShell."
    ),
)

_MOCK_RESPONSE = AnswerResponse(
    answer=(
        "SQL injection can be prevented primarily by using **prepared statements** "
        "(parameterized queries) [1]. These ensure that user input is never "
        "interpreted as SQL code. According to NIST SP 800-61r3, incidents involving "
        "SQL injection fall under the category of computer security policy violations "
        "and must be handled through the incident response lifecycle [2]. "
        "MITRE ATT&CK also documents SQL injection as a technique under the "
        "\"Execution\" tactic via scripting interpreters (T1059) [3]."
    ),
    citations=[
        Citation(
            id=1,
            chunk_id=_MOCK_CHUNK_1.chunk_id,
            title=_MOCK_CHUNK_1.title,
            source=_MOCK_CHUNK_1.source,
            section=_MOCK_CHUNK_1.section,
            url="https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
        ),
        Citation(
            id=2,
            chunk_id=_MOCK_CHUNK_2.chunk_id,
            title=_MOCK_CHUNK_2.title,
            source=_MOCK_CHUNK_2.source,
            section=_MOCK_CHUNK_2.section,
            url="https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf",
        ),
        Citation(
            id=3,
            chunk_id=_MOCK_CHUNK_3.chunk_id,
            title=_MOCK_CHUNK_3.title,
            source=_MOCK_CHUNK_3.source,
            section=_MOCK_CHUNK_3.section,
            url="https://attack.mitre.org/techniques/T1059/",
        ),
    ],
    chunks=[
        RetrievalResult(chunk=_MOCK_CHUNK_1, score=0.94),
        RetrievalResult(chunk=_MOCK_CHUNK_2, score=0.87),
        RetrievalResult(chunk=_MOCK_CHUNK_3, score=0.81),
    ],
    latency_ms=312,
    tokens=420,
    cost=0.0011,
    answerable=True,
)


def ask(question: str, filters: dict | None = None) -> AnswerResponse:
    """Send *question* to the backend and return an AnswerResponse.

    In mock mode (USE_MOCK=true) the question is ignored and a fixed response
    is returned so the UI can be developed and tested independently of the API.
    """
    if Config.USE_MOCK:
        return _MOCK_RESPONSE

    payload: dict = {"question": question}
    if filters:
        payload["filters"] = filters

    response = requests.post(
        f"{Config.API_URL}/ask",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return AnswerResponse.model_validate(response.json())
