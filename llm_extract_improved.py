# llm_extract_improved.py
import os, re, json
from pathlib import Path
from dotenv import load_dotenv

# Optional: use rapidfuzz if available
try:
    from rapidfuzz import fuzz
    def fuzzy_ratio(a,b): return fuzz.token_set_ratio(a or "", b or "")/100.0
except Exception:
    import difflib
    def fuzzy_ratio(a,b):
        return difflib.SequenceMatcher(None, (a or "").strip().lower(), (b or "").strip().lower()).ratio()

# Groq Chat (langchain_groq) used in your environment
try:
    from langchain_groq import ChatGroq
    HAS_GROQ = True
except Exception:
    HAS_GROQ = False

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL","llama3-8b-8192")

groq_chat = None
if HAS_GROQ and GROQ_API_KEY:
    groq_chat = ChatGroq(groq_api_key=GROQ_API_KEY, model_name=MODEL_NAME, temperature=0)
    print("Groq initialized:", MODEL_NAME)
else:
    print("Groq not initialized (no key or langchain_groq missing). Script will use heuristics only.")

RAW = Path("raw_ocr_output.txt").read_text(encoding="utf-8")
OUT_GOOD = "nism_questions_final_v2.json"
OUT_FALL = "nism_questions_fallback_v2.json"

# --- helpers ------------------------------------------------
def norm(s): 
    return re.sub(r'\s+', ' ', (s or "").replace('“','"').replace('”','"').replace('¥','').replace('%','')).strip()

def extract_json_from_text(resp_text):
    if not resp_text: return None
    s = resp_text.strip()
    # quick safe attempt
    try:
        return json.loads(s)
    except Exception:
        pass
    # find first JSON object substring by matching braces
    start = s.find('{')
    if start == -1: return None
    depth = 0
    end = -1
    for i in range(start, len(s)):
        if s[i] == '{': depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1: return None
    candidate = s[start:end+1]
    try:
        return json.loads(candidate)
    except Exception:
        # last resort: replace single quotes with double quotes (risky)
        try:
            return json.loads(candidate.replace("'", '"'))
        except Exception:
            return None

# improved splitter: top-level find question-numbered blocks
QNUM_RE = re.compile(r'(?m)^(?:Q\s*\d{1,3}|\d{1,4})[\).\s:-]+')

def split_into_blocks(text):
    # find positions of headings (Q7., 9., 240. etc)
    idxs = [m.start() for m in QNUM_RE.finditer(text)]
    if not idxs:
        # fallback: split by double newline into blocks
        return [b.strip() for b in re.split(r'\n{2,}', text) if b.strip()]
    idxs.append(len(text))
    blocks = []
    for i in range(len(idxs)-1):
        b = text[idxs[i]:idxs[i+1]].strip()
        if b:
            blocks.append(b)
    # further split blocks that contain multiple headings by searching inside
    final = []
    for b in blocks:
        # if block contains more than one heading inside, split
        inner = [(m.start(), m.group()) for m in QNUM_RE.finditer(b)]
        if len(inner) > 1:
            # use same method but relative to block
            starts = [m.start() for m in QNUM_RE.finditer(b)]
            starts.append(len(b))
            for j in range(len(starts)-1):
                sb = b[starts[j]:starts[j+1]].strip()
                if sb: final.append(sb)
        else:
            final.append(b)
    return final

def extract_question_options_explanation(block):
    """
    Given a block that should contain one question (or close to it),
    try to extract question text, dict of a,b,c,d options and explanation.
    """
    lines = [norm(l) for l in block.splitlines() if norm(l)!='']
    if not lines:
        return None, {}, ""
    # heuristic — find 'Explanation' index if present
    expl_idx = None
    for i,l in enumerate(lines):
        if re.search(r'(?i)^explanation[:\s]*', l) or re.search(r'(?i)\bEXPLANATION\b', l):
            expl_idx = i
            break
    explanation = ""
    if expl_idx is not None:
        explanation = " ".join(lines[expl_idx+1:]).strip()
        lines = lines[:expl_idx]  # shrink to before explanation
    # now find options — look for lettered options first
    options = {}
    qtext = ""
    # join lines into single text to find patterns
    joined = "\n".join(lines)
    # try find pattern lettered lines via regex
    lettered = re.findall(r'(?m)^\s*\(?([A-Da-d])\)?[\).:\s-]+(.+)', joined)
    if lettered and len(lettered) >= 2:
        # build options mapping by iterating lines and capturing multi-line continuation
        opts = {}
        current = None
        current_text = []
        for l in lines:
            m = re.match(r'^\s*\(?([A-Da-d])\)?[\).:\s-]+(.+)', l)
            if m:
                # flush previous
                if current:
                    opts[current] = " ".join(current_text).strip()
                current = m.group(1).lower()
                current_text = [m.group(2).strip()]
            else:
                # continuation if current exists
                if current:
                    current_text.append(l)
        if current:
            opts[current] = " ".join(current_text).strip()
        # qtext is lines before first option
        first_opt_index = None
        for i,l in enumerate(lines):
            if re.match(r'^\s*\(?[A-Da-d]\)?[\).:\s-]+', l):
                first_opt_index = i
                break
        qtext = " ".join(lines[:first_opt_index]).strip() if first_opt_index is not None else lines[0]
        # normalize into a,b,c,d
        options = {k: opts.get(k,"") for k in ['a','b','c','d']}
        return qtext, options, explanation
    # if lettered options not found, try to detect four option lines by short-line heuristic
    # find candidate option lines (short lines, not starting with CORRECT/WRONG)
    candidate_idx = []
    for i,l in enumerate(lines):
        if re.search(r'(?i)^(?:CORRECT|WRONG|EXPLANATION|% WRONG|X WRONG)', l):
            continue
        # treat lines with 1-8 words as option candidates (adjustable)
        if 1 <= len(l.split()) <= 10:
            candidate_idx.append(i)
    # try to find a group of 4 consecutive candidates
    chosen = None
    for start in range(0, len(candidate_idx)-3):
        if candidate_idx[start+3] - candidate_idx[start] <= 6:  # within 6 lines
            # ensure they are consecutive indices
            if candidate_idx[start+1]==candidate_idx[start]+1 and candidate_idx[start+2]==candidate_idx[start]+2 and candidate_idx[start+3]==candidate_idx[start]+3:
                chosen = candidate_idx[start:start+4]
                break
    if chosen is None and len(candidate_idx) >= 4:
        chosen = candidate_idx[:4]
    if chosen:
        opts = {}
        for idx,label in enumerate(['a','b','c','d']):
            opts[label] = lines[chosen[idx]]
        # question is everything before first chosen index
        qline_idx = chosen[0]
        qtext = " ".join(lines[:qline_idx]).strip()
        return qtext, opts, explanation
    # fallback: if no options found, return whole block as question text (user may fix manually)
    return (" ".join(lines)).strip(), {}, explanation

# LLM prompt with few-shot (strict JSON)
PROMPT_FEWSHOT = """You are an extractor. Input is a cleaned multiple-choice block.
Return ONLY valid JSON object with keys:
question (string), options (object with a,b,c,d), correct_option (a/b/c/d or empty), explanation (string).

Example input:
Question: Which color is the sky?
A) Green
B) Blue
C) Red
D) Yellow
Explanation:
Because the atmosphere scatters blue light.

Example output:
{{"question":"Which color is the sky?","options":{{"a":"Green","b":"Blue","c":"Red","d":"Yellow"}},"correct_option":"b","explanation":"Because the atmosphere scatters blue light."}}

Now process:
{block}
"""

def call_llm_for_block(block):
    if not groq_chat:
        return None, "no groq"
    try:
        resp = groq_chat.invoke(PROMPT_FEWSHOT.format(block=block))
        text = getattr(resp, "content", str(resp))
        parsed = extract_json_from_text(text)
        if parsed:
            return parsed, text
        # retry with smaller prompt
        resp2 = groq_chat.invoke("Extract JSON only. " + PROMPT_FEWSHOT.format(block=block), )
        text2 = getattr(resp2,"content",str(resp2))
        parsed2 = extract_json_from_text(text2)
        return parsed2, text2
    except Exception as e:
        return None, f"llm error: {e}"

# run processing
blocks = split_into_blocks(RAW)
print("Top-level candidate blocks:", len(blocks))

parsed = []
fallback = []

# map of found q numbers for reporting
found_qnumbers = set(re.findall(r'(?:Q\s*\d{1,3}|\d{1,4})', RAW))

for bidx, block in enumerate(blocks, start=1):
    # inside big blocks there might still be multiple Qnumbers - further split:
    inner_headers = [m.start() for m in QNUM_RE.finditer(block)]
    subblocks = []
    if len(inner_headers) > 1:
        # create smaller subblocks
        starts = inner_headers + [len(block)]
        for i in range(len(starts)-1):
            sb = block[starts[i]:starts[i+1]].strip()
            if sb: subblocks.append(sb)
    else:
        subblocks = [block]

    for sb in subblocks:
        qtext, options, explanation = extract_question_options_explanation(sb)
        compact_for_llm = f"Question: {qtext}\nA) {options.get('a','')}\nB) {options.get('b','')}\nC) {options.get('c','')}\nD) {options.get('d','')}\nExplanation:\n{explanation}"
        # if qtext looks like just "Q20." try to merge with neighbor text by searching nearby in original RAW
        if re.match(r'^\s*(?:Q\s*\d+|\d{1,4})[\).\s:-]*$', qtext):
            # attempt to attach next nonempty lines from RAW (best-effort)
            # locate sb in RAW and extend a few lines forward
            pos = RAW.find(sb)
            if pos != -1:
                tail = RAW[pos:pos+1000]  # small window
                # try to find next question-like sentence inside tail beyond heading
                more = re.sub(r'^\s*(?:Q\s*\d+|\d{1,4})[\).\s:-]+','', tail).strip()
                if len(more) > 20:
                    qtext2, options2, explanation2 = extract_question_options_explanation(more)
                    if len(options2) >= 2:
                        qtext, options, explanation = qtext2, options2, explanation2
                        compact_for_llm = f"Question: {qtext}\nA) {options.get('a','')}\nB) {options.get('b','')}\nC) {options.get('c','')}\nD) {options.get('d','')}\nExplanation:\n{explanation}"

        # Try LLM extraction if available and we have at least one option
        parsed_json, llm_raw = None, ""
        if groq_chat and (options.get('a') or options.get('b') or options.get('c') or options.get('d')):
            parsed_json, llm_raw = call_llm_for_block(compact_for_llm)

        # Validate LLM output
        accepted = False
        if isinstance(parsed_json, dict) and parsed_json.get('question'):
            # ensure options exist (fill from heuristics if LLM missed)
            opts = parsed_json.get('options', {})
            if not isinstance(opts, dict):
                opts = {}
            for k in ['a','b','c','d']:
                if not opts.get(k):
                    opts[k] = options.get(k,"")
            parsed_json['options'] = opts
            if 'explanation' not in parsed_json or not parsed_json['explanation']:
                parsed_json['explanation'] = explanation
            accepted = True

        if accepted:
            parsed.append(parsed_json)
            continue

        # fallback inference: try to deduce correct option from explicit "CORRECT ANSWER" in sb
        marked = ""
        m = re.search(r'(?i)CORRECT\s*ANSWER[:\s-]*(.*)', sb)
        if m:
            marked = m.group(1).strip()
            if not marked:
                # maybe next line has it
                after = sb.splitlines()
                try:
                    idx = [i for i,l in enumerate(after) if re.search(r'(?i)CORRECT\s*ANSWER', l)][0]
                    if idx+1 < len(after): marked = after[idx+1].strip()
                except Exception:
                    pass
        candidate_letter = ""
        if marked:
            mm = re.search(r'([A-Da-d])\b', marked)
            if mm:
                candidate_letter = mm.group(1).lower()
            else:
                # fuzzy match marked text to options
                best,score = "",0.0
                for k,v in options.items():
                    s = fuzzy_ratio(v, marked)
                    if s > score:
                        best,score = k,s
                if score > 0.7:
                    candidate_letter = best
        # try explanation fuzzy match if still nothing
        if not candidate_letter and explanation:
            best,score = "",0.0
            for k,v in options.items():
                s = fuzzy_ratio(v, explanation)
                if s > score:
                    best,score = k,s
            if score > 0.7: candidate_letter = best

        rec = {
            "question": qtext,
            "options": options,
            "correct_option": candidate_letter,
            "explanation": explanation,
            "llm_raw": llm_raw
        }
        # if we have a candidate letter or at least some options, keep as parsed; otherwise fallback
        if candidate_letter or any(options.values()):
            parsed.append(rec)
        else:
            fallback.append(rec)

# save results
Path(OUT_GOOD).write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
Path(OUT_FALL).write_text(json.dumps(fallback, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved {len(parsed)} parsed questions -> {OUT_GOOD}")
print(f"Saved {len(fallback)} fallback items -> {OUT_FALL}")
