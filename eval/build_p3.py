"""Build data/eval/questions_p3.jsonl from hand-written items.

Each item has a question, an answer, a doc id, and two short anchor phrases (start, end) copied from the
document. The script finds them in YOUR data/processed/documents.jsonl and takes the exact text between
them as source_passage, so validate.py's "exact passage" check passes.

    python3 -m eval.build_p3
    python3 data/eval/validate.py data/eval/questions_p3.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DOCS = Path("data/processed/documents.jsonl")
OUT = Path("data/eval/questions_p3.jsonl")
MAX_PASSAGE = 900

P = "owasp-password-storage-cheat-sheet"
SQL = "owasp-sql-injection-prevention-cheat-sheet"
SES = "owasp-session-management-cheat-sheet"
CJ = "owasp-clickjacking-defense-cheat-sheet"
HSTS = "owasp-http-strict-transport-security-cheat-sheet"
MFA = "owasp-multifactor-authentication-cheat-sheet"
FP = "owasp-forgot-password-cheat-sheet"
FU = "owasp-file-upload-cheat-sheet"
DK = "owasp-docker-security-cheat-sheet"
SEC = "owasp-secrets-management-cheat-sheet"
ERR = "owasp-error-handling-cheat-sheet"
IV = "owasp-input-validation-cheat-sheet"
CSP = "owasp-content-security-policy-cheat-sheet"
CRY = "owasp-cryptographic-storage-cheat-sheet"

# (type, doc_id, question, answer, start_phrase, end_phrase)
ITEMS = [
 ("definition", P, "Which hashing algorithms does the OWASP Password Storage Cheat Sheet recommend for protecting stored passwords?",
  "Strong, slow hashing algorithms such as Argon2id, bcrypt or PBKDF2, with a unique salt per password; passwords must never be stored in plain text.",
  "Passwords should never be stored in plain text.", "such as Argon2id, bcrypt, or PBKDF2."),
 ("procedure", P, "What minimum Argon2id configuration does the Password Storage Cheat Sheet recommend?",
  "At least 19 MiB of memory, an iteration count of 2, and 1 degree of parallelism.",
  "with a minimum configuration of 19 MiB", "1 degree of parallelism."),
 ("procedure", P, "What bcrypt work factor and password length limit are recommended for legacy systems?",
  "A work factor of 10 or more, with a password limit of 72 bytes.",
  "use a work factor of 10 or more", "password limit of 72 bytes."),
 ("definition", P, "Why is hashing preferred over encryption for storing passwords?",
  "Hashing is one-way, so even if an attacker obtains the hashed password they cannot use it to log in as the victim.",
  "Even if an attacker obtains the hashed password", "log in as the victim."),
 ("definition", SQL, "Under what condition can an attacker use SQL injection against an application?",
  "When the application has dynamic database queries that use string concatenation and user-supplied input.",
  "Attackers can use SQL injection", "user-supplied input."),
 ("definition", SQL, "Why do prepared statements with parameterized queries protect against SQL injection?",
  "The developer defines all the SQL code first and passes each parameter later, so the database always distinguishes code from data whatever the user input is.",
  "Prepared statements are simple to write", "regardless of what user input is supplied."),
 ("definition", SES, "Once an authenticated session is established, what is the session ID equivalent to?",
  "It is temporarily equivalent to the strongest authentication method used by the application, such as a password, OTP, certificate, smartcard or biometrics.",
  "Once an authenticated session has been established", "biometrics (such as fingerprint or eye retina)."),
 ("definition", SES, "Why does a web application need session management when HTTP is stateless?",
  "Each HTTP request and response pair is independent, so session management is needed to link the authentication and access control modules across requests.",
  "HTTP is a stateless protocol", "commonly available in web applications"),
 ("multi-part", CJ, "What are the three main mechanisms for defending against clickjacking?",
  "Blocking framing with the X-Frame-Options or CSP frame-ancestors headers, using the SameSite cookie attribute, and adding JavaScript frame-busting code.",
  "Preventing the browser from loading the page in frame", "to attempt to prevent it being loaded in a frame"),
 ("procedure", CJ, "What does the Content-Security-Policy frame-ancestors 'none' directive do, and when is it recommended?",
  "It prevents any domain from framing the content, and it is recommended unless a specific need for framing has been identified.",
  "This prevents any domain from framing the content.", "specific need has been identified for framing."),
 ("definition", HSTS, "What does the HTTP Strict Transport Security header make a supported browser do?",
  "It makes the browser send all communications to the domain over HTTPS and prevents any communication over HTTP.",
  "is an opt-in security enhancement", "send all communications over HTTPS."),
 ("time-based", HSTS, "When was HSTS published as a specification, and under which RFC?",
  "It was published at the end of 2012 as RFC 6797 by the IETF.",
  "published end of 2012 as", "by the IETF."),
 ("time-based", HSTS, "What max-age value does the OWASP HSTS example use for a long duration of two years?",
  "63072000 seconds.",
  "This example sets a long", "63072000 seconds) max-age for the issuing host."),
 ("definition", MFA, "What does multifactor authentication require, and which factor categories exist?",
  "Evidence from at least two distinct factors: something you know, something you have, and something you are.",
  "requires evidence from at least two distinct authentication factors", "something you are."),
 ("definition", MFA, "Does requiring both a password and a PIN count as multifactor authentication?",
  "No. Multiple instances of the same factor do not constitute MFA and add minimal security.",
  "requiring multiple instances of the same authentication factor", "offers minimal additional security."),
 ("multi-part", MFA, "Which password attacks does MFA defend against, and what does Microsoft's analysis suggest about its effect?",
  "It defends against brute-force, credential stuffing and password spraying, and Microsoft's analysis suggests it would have stopped 99.9% of account compromises.",
  "MFA is by far the best defense against the majority of password-related attacks", "99.9%"),
 ("definition", FP, "Why is the forgot password functionality a common source of vulnerabilities?",
  "Although it looks straightforward, it is prone to flaws such as the renowned user enumeration attack.",
  "Even though this functionality looks straightforward", "user enumeration attack"),
 ("multi-part", FP, "What protection should a forgot password request have against excessive automated submissions, and why?",
  "Rate-limiting per account, a CAPTCHA or other controls, because otherwise an attacker could flood the user's email or SMS with useless reset requests.",
  "Implement protections against excessive automated submissions", "with useless requests."),
 ("multi-part", FU, "What availability threats can malicious file uploads cause?",
  "Attackers can send ZIP bombs, XML bombs (billion laughs) or huge files to fill the server storage and damage availability.",
  "Send ZIP bombs, XML bombs", "in a way to fill the server storage"),
 ("definition", DK, "Why is exposing the Docker daemon socket dangerous?",
  "Access to the socket is equivalent to giving unrestricted root access to the host.",
  "Giving someone access to it", "unrestricted root access to your host."),
 ("definition", DK, "Why does a vulnerable host kernel put Docker containers at risk?",
  "Containers share the host kernel, so if the kernel is vulnerable the containers are also vulnerable.",
  "containers share the host", "the containers are also vulnerable."),
 ("definition", SEC, "What common problem does the Secrets Management Cheat Sheet describe about how organizations store secrets?",
  "Many organizations hardcode secrets in plaintext in source code and scatter them across configuration files and configuration management tools.",
  "Many organizations have them hardcoded within the source code in plaintext", "configuration management tools."),
 ("definition", ERR, "How can unhandled errors help an attacker?",
  "They help the attacker's initial reconnaissance phase, which is very important for the rest of the attack.",
  "Unhandled errors can assist an attacker in this initial phase", "rest of the attack."),
 ("multi-part", IV, "What two kinds of checks should input validation cover?",
  "Syntax (the expected type and format) and semantics (whether the value makes sense for the operation).",
  "(the expected type and format)", "whether the value makes sense for the operation"),
 ("definition", IV, "Why should input validation use an allowlist rather than trying to recognize malicious strings?",
  "Define what the application accepts and reject everything else; trying to recognize every malicious string does not work, for example blocking apostrophes rejects legitimate names without making a query safe.",
  "Define what the application accepts and reject values outside those rules.", "Do not try to recognize every malicious string."),
 ("definition", CSP, "Does a Content Security Policy prevent web applications from containing vulnerabilities?",
  "No. It provides a second layer of protection that makes vulnerabilities, especially XSS, significantly more difficult to exploit.",
  "of protection against various types of vulnerabilities", "difficult for an attacker to exploit."),
 ("procedure", CRY, "Which algorithm and key size does the Cryptographic Storage Cheat Sheet prefer for symmetric encryption?",
  "AES with a key of at least 128 bits (ideally 256 bits) and a secure mode.",
  "For symmetric encryption", "should be used as the preferred algorithm."),
]

UNANSWERABLE = [
 "What is the current price of a Burp Suite Professional license?",
 "Which Kubernetes admission controller does NIST SP 800-61 Rev 3 require for container deployments?",
 "What is the maximum bcrypt work factor the OWASP Password Storage Cheat Sheet allows?",
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def pattern(phrase: str) -> re.Pattern:
    return re.compile(r"\s+".join(re.escape(w) for w in phrase.split()), re.I)


def main() -> int:
    docs = {}
    for line in DOCS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            docs[d["doc_id"]] = d["text"]

    rows, bad = [], []
    for i, (qtype, doc_id, q, a, start, end) in enumerate(ITEMS, start=1):
        text = docs.get(doc_id)
        if text is None:
            bad.append((i, f"doc not found: {doc_id}")); continue
        m1 = pattern(start).search(text)
        m2 = pattern(end).search(text, m1.start()) if m1 else None
        if not m1 or not m2:
            bad.append((i, f"anchor not found in {doc_id}: {'start' if not m1 else 'end'}")); continue
        passage = norm(text[m1.start(): m2.end()])
        if len(passage) > MAX_PASSAGE:
            bad.append((i, f"passage too long ({len(passage)} chars)")); continue
        rows.append({"id": f"p3-{i:02d}", "question": q, "answer": a,
                     "source_doc": doc_id, "source_passage": passage, "type": qtype})

    n = len(ITEMS)
    for j, q in enumerate(UNANSWERABLE, start=1):
        rows.append({"id": f"p3-unans-{j:02d}", "question": q, "answer": "I don't know",
                     "source_doc": "", "source_passage": "", "type": "unanswerable"})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} questions to {OUT}")
    for i, why in bad:
        print(f"  SKIPPED item {i}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())