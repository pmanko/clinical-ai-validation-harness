#!/usr/bin/env python3

import sys
import textwrap

def main():
    print("==========================================================")
    print(" Query Preprocessing Modernization Demo")
    print("==========================================================")
    print(textwrap.fill(
        "This demo illustrates why we removed stopword stripping from the "
        "OpenMRS QueryStore, preparing it for modern multilingual dense "
        "embeddings (like multilingual-e5).", width=70
    ))
    print()

    queries = [
        ("Is the patient responding to metformin?", True),
        ("Is the patient NOT responding to metformin?", False),
        ("Patient well controlled on current dose", True),
        ("Patient NOT well controlled on current dose", False)
    ]

    print("--- 1. Legacy Behavior (With Stopword Stripping) ---")
    print("In the legacy system, words like 'is', 'the', 'to', 'on', and 'not' were stripped.")
    for query, _ in queries:
        # Simulate legacy stripping
        stripped = " ".join([w for w in query.split() if w.lower() not in ['is', 'the', 'to', 'on', 'not']])
        print(f"  Raw:      {query}")
        print(f"  Stripped: {stripped}")
        print()

    print(textwrap.fill(
        "Notice how 'NOT responding' and 'responding' both become 'patient responding metformin'. "
        "The clinical intent is completely destroyed.", width=70
    ))
    print()

    print("--- 2. Modern Behavior (Natural Context Preservation) ---")
    print("The new pipeline preserves the exact grammatical structure for the embedding model.")
    for query, _ in queries:
        print(f"  Raw Query passed to multilingual-e5: 'query: {query}'")
        
    print()
    print("Conclusion: By preserving the natural language sentence, the dense ")
    print("embedding model can use its self-attention mechanism to correctly ")
    print("differentiate between a patient who is responding and one who is not.")
    print("==========================================================")


if __name__ == "__main__":
    main()
