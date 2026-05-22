"""
Chronicle of Skills — AI Quest Generator
------------------------------------------
Uses Google Gemini (free, no credit card) or Groq (free, fast)
to generate new quests based on what's already in your Supabase DB.

GET YOUR FREE API KEYS:
  Gemini → https://aistudio.google.com/app/apikey          (no credit card)
  Groq   → https://console.groq.com/keys                   (no credit card)

Usage:
  python generate_quests.py --url YOUR_SUPABASE_URL --key YOUR_SERVICE_ROLE_KEY

  

Options:
  --provider gemini|groq   Which AI to use (default: gemini)
  --gemini-key KEY         Gemini API key (or set GEMINI_API_KEY env var)
  --groq-key KEY           Groq API key   (or set GROQ_API_KEY env var)
  --count N                How many new quests to generate (default: 10)
  --dry-run                Preview without inserting into DB
"""

import argparse
import json
import os
import re
import sys
from supabase import create_client

VALID_TIERS = {"common", "uncommon", "rare", "legendary"}
VALID_CATEGORIES = {
    "Programming", "Physical", "Intellect", "Worldly",
    "Life", "Social", "Creative", "Challenge", "Weekly"
}
XP_MAP = {"common": 50, "uncommon": 120, "rare": 250, "legendary": 500}

SYSTEM_PROMPT = """You are the Lorekeeper of the Chronicle of Skills — an RPG quest system for two real friends, Uriel and Guy.

Generate new quests. Each quest must:
- Be a REAL, doable challenge in everyday life (not fantasy — actual things people do)
- Have a short evocative lore line (max 12 words, poetic/dramatic, first-person or philosophical tone)
- Have a clear description of exactly what to do (1-2 sentences, specific and measurable)
- Fit one category: Programming, Physical, Intellect, Worldly, Life, Social, Creative, Challenge, Weekly
- Have a tier: common (easy, ~30min), uncommon (moderate effort), rare (hard/real commitment), legendary (major achievement)

Good quest ideas: learning instruments, walking with no phone, cooking from scratch, reading books,
building projects, journaling, languages, cold showers, photography, financial planning, stargazing,
drawing, teaching others, meditation, exploring new places, writing stories, composing music, digital detoxes.

NEVER repeat quests from the existing list.
NEVER make vague or unmeasurable quests.
DO NOT use the word "embark".
"""

def build_prompt(existing, count):
    lines = "\n".join(
        f"- [{q['tier']}] [{q['category']}] {q['name']}: {q['description']}"
        for q in existing
    )
    return f"""Quests already in the Chronicle (do not duplicate):

{lines}

Generate {count} NEW quests that differ in theme, category, and difficulty from the above.
Spread across different categories. Make them vivid and specific.

Respond ONLY with a raw JSON array — no explanation, no markdown, no code fences.

[
  {{
    "name": "Quest Name",
    "lore": "Short dramatic flavour line, max 12 words.",
    "description": "Exactly what to do. Specific and measurable.",
    "category": "Category",
    "tier": "tier"
  }}
]"""

def extract_json(text):
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None

# ── PROVIDERS ──────────────────────────────────────────────────────────────

def call_gemini(api_key, existing, count):
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    print("  Calling Google Gemini (gemini-2.0-flash)…")
    response = model.generate_content(build_prompt(existing, count))
    return response.text

def call_groq(api_key, existing, count):
    from groq import Groq
    client = Groq(api_key=api_key)
    print("  Calling Groq (llama-3.3-70b-versatile)…")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_prompt(existing, count)},
        ],
        temperature=0.9,
    )
    return response.choices[0].message.content

# ── VALIDATION ─────────────────────────────────────────────────────────────

def validate(q):
    errors = []
    if not isinstance(q.get("name"), str) or not q["name"].strip():
        errors.append("missing name")
    if not isinstance(q.get("lore"), str) or not q["lore"].strip():
        errors.append("missing lore")
    if not isinstance(q.get("description"), str) or not q["description"].strip():
        errors.append("missing description")
    if q.get("tier", "").lower() not in VALID_TIERS:
        errors.append(f"invalid tier '{q.get('tier')}' — must be: {', '.join(sorted(VALID_TIERS))}")
    if q.get("category", "") not in VALID_CATEGORIES:
        errors.append(f"invalid category '{q.get('category')}' — must be: {', '.join(sorted(VALID_CATEGORIES))}")
    return errors

# ── MAIN ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Chronicle of Skills — AI Quest Generator")
    parser.add_argument("--url",        required=True, help="Supabase project URL")
    parser.add_argument("--key",        required=True, help="Supabase service role key")
    parser.add_argument("--provider",   default="gemini", choices=["gemini", "groq"], help="AI provider (default: gemini)")
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"), help="Gemini API key")
    parser.add_argument("--groq-key",   default=os.environ.get("GROQ_API_KEY"),   help="Groq API key")
    parser.add_argument("--count",      type=int, default=10, help="Quests to generate (default: 10)")
    parser.add_argument("--dry-run",    action="store_true", help="Preview without inserting")
    args = parser.parse_args()

    # Check API key is present
    if args.provider == "gemini" and not args.gemini_key:
        print("\n  ERROR: No Gemini API key provided.")
        print("  Get one free at: https://aistudio.google.com/app/apikey")
        print("  Then pass it with --gemini-key YOUR_KEY or set GEMINI_API_KEY env var.\n")
        sys.exit(1)
    if args.provider == "groq" and not args.groq_key:
        print("\n  ERROR: No Groq API key provided.")
        print("  Get one free at: https://console.groq.com/keys")
        print("  Then pass it with --groq-key YOUR_KEY or set GROQ_API_KEY env var.\n")
        sys.exit(1)

    sb = create_client(args.url, args.key)

    print("\n── Chronicle of Skills — AI Quest Generator ─────────────────\n")

    # 1. Read existing quests
    res = sb.table("quests").select("name, lore, description, category, tier").execute()
    existing = res.data or []
    existing_names = {q["name"].strip().lower() for q in existing}
    print(f"  Existing quests in DB : {len(existing)}")
    print(f"  Provider              : {args.provider}")
    print(f"  Requesting            : {args.count} new quests")

    # 2. Call AI
    try:
        raw = call_gemini(args.gemini_key, existing, args.count) if args.provider == "gemini" \
              else call_groq(args.groq_key, existing, args.count)
    except Exception as e:
        print(f"\n  ERROR calling {args.provider}: {e}\n")
        sys.exit(1)

    print(f"  Response received     : {len(raw)} chars")

    # 3. Parse
    quests = extract_json(raw)
    if not quests or not isinstance(quests, list):
        print("\n  ERROR: Could not parse a JSON array from the model response.")
        print("  Raw output:\n")
        print(raw)
        sys.exit(1)

    # 4. Validate + deduplicate
    valid, skipped = [], []
    for q in quests:
        q = {k: (v.strip() if isinstance(v, str) else v) for k, v in q.items()}
        q["tier"] = q.get("tier", "").lower()

        if q.get("name", "").lower() in existing_names:
            skipped.append((q.get("name", "?"), ["duplicate name"]))
            continue

        errs = validate(q)
        if errs:
            skipped.append((q.get("name", "?"), errs))
        else:
            valid.append(q)
            existing_names.add(q["name"].lower())  # prevent intra-batch dupes

    print(f"  Valid & new           : {len(valid)}")
    if skipped:
        print(f"  Skipped               : {len(skipped)}")
        for name, reasons in skipped:
            print(f"    ✗ {name} — {', '.join(reasons)}")

    if not valid:
        print("\n  Nothing valid to insert. Try running again.\n")
        return

    # 5. Preview
    print("\n  Quests to insert:\n")
    for q in valid:
        xp = XP_MAP.get(q["tier"], "?")
        print(f"  [{q['tier']:10s}] [{q['category']:12s}] +{xp} XP")
        print(f"    {q['name']}")
        print(f"    \"{q['lore']}\"")
        print(f"    → {q['description']}\n")

    if args.dry_run:
        print("  [DRY RUN] No changes made.\n")
        return

    # 6. Insert
    sb.table("quests").insert(valid).execute()
    print(f"  ✓ Inserted {len(valid)} new quests.")

    total = sb.table("quests").select("id").execute()
    print(f"  Total quests in DB    : {len(total.data or [])}")
    print("\n── Done ─────────────────────────────────────────────────────\n")

if __name__ == "__main__":
    main()
