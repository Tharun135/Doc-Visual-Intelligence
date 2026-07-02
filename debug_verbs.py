from generators.architecture_parser import RELATIONSHIP_VERBS
import re

test_content = '''
The Edge Device receives data from sensors and sends it to the Connector.

The Connector transforms data and uploads it to the Server.

The Server processes data and writes results to a Database.

The Database exports reports to an external Cloud service using HTTPS.

The UI Dashboard displays data from the Server in real-time.
'''

# Test specific relationship extraction
print("Testing relationship verb matching:")
test_sentences = [
    "Edge Device receives data from sensors",
    "sends it to the Connector",
    "uploads it to the Server",
    "writes results to a Database",
    "exports reports to an external Cloud service",
]

for sentence in test_sentences:
    print(f"\nSentence: {sentence}")
    found = []
    for verb_phrase in RELATIONSHIP_VERBS.keys():
        if verb_phrase.lower() in sentence.lower():
            found.append(verb_phrase)
    if found:
        print(f"  Found: {found}")
    else:
        print(f"  NOT FOUND")
