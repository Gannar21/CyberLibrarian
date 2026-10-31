import json
import re
from pathlib import Path

DOCS_PATH = Path("data/sample/documents_sample.jsonl")
OUTPUT_PATH = Path("data/eval/questions_p2.jsonl")


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text):
    return set(re.findall(r"\b[a-zA-Z0-9]+\b", text.lower()))


def find_passage(documents, doc_id, phrase):
    if doc_id not in documents:
        raise ValueError(f"Document not found: {doc_id}")

    text = normalize(documents[doc_id])
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # Search for the phrase directly, ignoring Markdown link formatting.
    phrase_words = tokenize(phrase)
    best_sentence = None
    best_score = 0

    for sentence in sentences:
        searchable = re.sub(
            r"\[([^\]]+)\]\([^)]+\)", r"\1", sentence
        )
        searchable = searchable.replace("**", "").replace("*", "")

        if phrase.lower() in searchable.lower():
            return sentence

        score = len(phrase_words & tokenize(searchable))

        if score > best_score:
            best_score = score
            best_sentence = sentence

    if best_sentence is None or best_score == 0:
        raise ValueError(
            f"Could not find a supporting passage in {doc_id} "
            f"for: {phrase}"
        )

    return best_sentence


questions_data = [
    (
        "01", "owasp-abuse-case-cheat-sheet",
        "Why are generic security requirements insufficient?",
        "They are too vague to provide useful guidance to a development team.",
        "security requirements generic development team", "definition"
    ),
    (
        "02", "owasp-abuse-case-cheat-sheet",
        "How should a team identify the attacks its application must defend against?",
        "The team should consider the application's business and technical context.",
        "attacks application business technical context", "procedure"
    ),
    (
        "03", "owasp-abuse-case-cheat-sheet",
        "What security technique is discussed in the OWASP Abuse Case Cheat Sheet?",
        "Abuse cases are a threat-modeling technique for identifying attacks against an application.",
        "abuse cases threat modeling technique", "definition"
    ),
    (
        "04", "owasp-abuse-case-cheat-sheet",
        "What is the objective of the OWASP Abuse Case Cheat Sheet?",
        "It explains abuse cases, their importance, and a practical approach to identifying and tracking them.",
        "objective cheat sheet abuse case", "definition"
    ),
    (
        "05", "owasp-abuse-case-cheat-sheet",
        "Why should attacks be identified during project or sprint planning?",
        "Identifying attacks helps teams evaluate business risks and prioritize security work.",
        "business risk identified attacks project sprint", "multi-part"
    ),
    (
        "06", "owasp-ai-powered-advertising-systems-security-cheat-sheet",
        "What kind of decisions do modern AI-powered advertising platforms make for each ad request?",
        "They make AI-driven financial decisions.",
        "AI-driven financial decisions ad request", "definition"
    ),
    (
        "07", "owasp-ai-powered-advertising-systems-security-cheat-sheet",
        "Which types of AI systems does the advertising security cheat sheet cover?",
        "It covers classical machine learning and generative AI, including LLMs and VLMs.",
        "classical ML generative AI LLMs VLMs", "definition"
    ),
    (
        "08", "owasp-ai-powered-advertising-systems-security-cheat-sheet",
        "When can AI-based personalization or targeting constitute profiling under GDPR Article 4(4)?",
        "When personalization, targeting, ranking, or lookalike models use personal data.",
        "personalization targeting ranking lookalike personal data profiling", "definition"
    ),
    (
        "09", "owasp-ai-powered-advertising-systems-security-cheat-sheet",
        "When can consent requirements apply even if an AI model does not run?",
        "Consent requirements can apply to storing or accessing information even when no model runs.",
        "consent storage access model runs", "definition"
    ),
    (
        "10", "owasp-ai-powered-advertising-systems-security-cheat-sheet",
        "What is the security objective of the AI-powered advertising cheat sheet?",
        "It provides security controls to help prevent AI systems from becoming an attack surface.",
        "security controls AI attack surface", "definition"
    ),
    (
        "11", "mitre-T1055.011",
        "What is Extra Window Memory Injection?",
        "It is a technique in which adversaries inject malicious code into a separate process using Extra Window Memory.",
        "Extra Window Memory Injection malicious code", "definition"
    ),
    (
        "12", "mitre-T1055.011",
        "What are two possible goals of Extra Window Memory Injection?",
        "Adversaries may use it to evade process-based defenses and potentially elevate privileges.",
        "evade process-based defenses elevate privileges", "multi-part"
    ),
    (
        "13", "mitre-T1055.011",
        "Where can code execute when an adversary uses Extra Window Memory Injection?",
        "The code can execute in the address space of a separate live process.",
        "arbitrary code address space separate live process", "definition"
    ),
    (
        "14", "mitre-T1055.011",
        "How might malware use a pointer stored in Extra Window Memory?",
        "It may place a pointer to malicious code in Extra Window Memory and transfer execution to that address.",
        "pointer code EWM execution address", "procedure"
    ),
    (
        "15", "mitre-T1055.011",
        "Why might Extra Window Memory Injection evade detection?",
        "The execution may be masked under a legitimate process.",
        "execution masked legitimate process", "definition"
    ),
    (
        "16", "mitre-T1055.011",
        "What kinds of events can endpoint behavior prevention analyze?",
        "It can analyze processes, files, API calls, and other endpoint events.",
        "processes files API calls endpoint events", "multi-part"
    ),
    (
        "17", "mitre-T1053.005",
        "What does the Scheduled Task technique describe?",
        "It describes adversaries abusing Windows Task Scheduler to schedule malicious code execution.",
        "Windows Task Scheduler malicious code execution", "definition"
    ),
    (
        "18", "mitre-T1053.005",
        "How can adversaries use scheduled tasks to maintain persistence?",
        "They can schedule programs to run at startup or at specified times.",
        "startup scheduled persistence", "procedure"
    ),
    (
        "19", "mitre-T1053.005",
        "Which utility can be used to manage scheduled tasks from the Windows command line?",
        "The schtasks utility can be run from the command line.",
        "schtasks command line", "definition"
    ),
    (
        "20", "mitre-T1053.005",
        "Why can hidden scheduled tasks be difficult for defenders to discover?",
        "Some hidden tasks may not appear in defender tools or manual queries.",
        "hidden tasks defender tools manual queries", "definition"
    ),
    (
        "21", "mitre-T1053.005",
        "What permissions are required for the described Security Descriptor registry modification?",
        "The described method requires SYSTEM permissions.",
        "Security Descriptor registry SYSTEM permissions", "definition"
    ),
    (
        "22", "mitre-T1205.002",
        "What is the Socket Filters technique?",
        "Adversaries attach filters to network sockets to monitor for packets that can activate backdoors.",
        "socket filters network packets backdoors", "definition"
    ),
    (
        "23", "mitre-T1205.002",
        "What can a matching packet trigger when a malicious socket filter is installed?",
        "It can trigger an action such as activating a reverse shell.",
        "matching packet trigger reverse shell", "definition"
    ),
    (
        "24", "mitre-T1205.002",
        "Why can malicious socket filters be difficult to detect?",
        "They may remain inactive until a matching packet arrives and may have low CPU overhead and limited visibility.",
        "socket filters low CPU limited visibility packet", "multi-part"
    ),
    (
        "25", "mitre-T1205.002",
        "What network traffic does the Socket Filters mitigation recommend filtering?",
        "It recommends filtering ingress, egress, and lateral network traffic.",
        "filter ingress egress lateral network traffic", "procedure"
    ),
]


def main():
    if not DOCS_PATH.exists():
        raise FileNotFoundError(
            f"Sample corpus not found: {DOCS_PATH}"
        )

    documents = {}

    with DOCS_PATH.open(encoding="utf-8-sig") as file:
        for line in file:
            if line.strip():
                doc = json.loads(line)
                documents[doc["doc_id"]] = doc["text"]

    results = []

    for qid, doc_id, question, answer, phrase, qtype in questions_data:
        passage = find_passage(documents, doc_id, phrase)

        # Verify that the passage exists in the original document.
        if passage not in normalize(documents[doc_id]):
            raise ValueError(
                f"Passage verification failed for question {qid}"
            )

        results.append({
            "id": f"p2-{qid}",
            "question": question,
            "answer": answer,
            "source_doc": doc_id,
            "source_passage": passage,
            "type": qtype,
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for item in results:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Created {OUTPUT_PATH} with {len(results)} questions.")


if __name__ == "__main__":
    main()