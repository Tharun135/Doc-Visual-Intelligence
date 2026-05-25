import json
import re


# --------------------------------------
# Load rules
# --------------------------------------

with open("rules/visual_rules.json", "r") as file:
    rules = json.load(file)


# --------------------------------------
# Count procedure steps
# --------------------------------------

def count_steps(content):

    patterns = [

        r'^\d+\.',          # 1.
        r'^step\s+\d+',     # Step 1
        r'^\d+\)'           # 1)

    ]

    total = 0

    for pattern in patterns:

        matches = re.findall(
            pattern,
            content,
            re.MULTILINE | re.IGNORECASE
        )

        total += len(matches)

    return total


# --------------------------------------
# Detect visual opportunities
# --------------------------------------

def detect_visuals(title, content):

    results = []

    content_lower = content.lower()
    title_lower = title.lower()

    step_count = count_steps(
        content
    )

    word_count = len(
        content.split()
    )


    print("\n=================")
    print("Content Preview:")
    print(content[:250])

    print("\nSteps:", step_count)
    print("Words:", word_count)

    print("=================")


    for rule in rules:

        score = 0

        evidence = []

        matched_keywords = []


        # ----------------------------------
        # Keyword matching
        # ----------------------------------

        keywords = rule.get(
            "keywords",
            []
        )

        for keyword in keywords:

            pattern = (

                r'\b'

                + re.escape(
                    keyword.lower()
                )

                + r'\b'
            )

            if re.search(
                pattern,
                content_lower
            ):

                matched_keywords.append(
                    keyword
                )


        # ----------------------------------
        # Keyword score
        # ----------------------------------

        if matched_keywords:

            weight = rule.get(
                "weight",
                1
            )

            score += (

                weight *

                len(
                    matched_keywords
                )
            )

            evidence.append(

                "Keywords: "

                +

                ", ".join(
                    matched_keywords
                )

            )


        # ----------------------------------
        # Procedure scoring
        # ----------------------------------

        if step_count >= 5:

            if (

                rule[
                    "visual_type"
                ]

                == "Flowchart"

            ):

                score += 4

                evidence.append(

                    f"{step_count} steps detected"

                )


        elif step_count >= 2:

            if (

                rule[
                    "visual_type"
                ]

                == "Screenshot"

            ):

                score += 2

                evidence.append(

                    f"{step_count} UI steps detected"

                )


        # ----------------------------------
        # Long content scoring
        # ----------------------------------

        min_words = rule.get(
            "min_words"
        )

        if (

            min_words

            and

            word_count >= min_words

        ):

            score += 1

            evidence.append(

                f"{word_count} words detected"

            )


        # ----------------------------------
        # Smart recommendation logic
        # ----------------------------------

        # Long UI procedures
        # prefer GIF over Screenshot

        if (

            rule["visual_type"]

            == "Screenshot"

            and

            step_count >= 6

        ):

            score = max(
                score - 2,
                1
            )


        if (

            rule["visual_type"]

            == "GIF Tutorial"

            and

            step_count >= 6

        ):

            score += 4

            evidence.append(
                "Long interactive workflow"
            )


        # Suppress flowchart
        # for Result sections

        if (

            rule["visual_type"]

            == "Flowchart"

            and

            "result" in content_lower

        ):

            score = 0

        # Suppress architecture diagrams
        # inside procedures

        if (

            rule["visual_type"]

            == "Architecture Diagram"

            and

            step_count >= 3

        ):

            score = 0

        # ----------------------------------
        # Section-aware filtering
        # ----------------------------------

        # Procedures prioritize workflow visuals

        if (

            "procedure" in title_lower

        ):

            if (

                rule["visual_type"]

                in [

                    "Architecture Diagram",
                    "Decision Tree"

                ]

            ):

                score = 0


        # Result sections usually do not
        # require visuals

        if (

            "result" in title_lower

        ):

            score = 0


        # Requirement sections usually
        # avoid screenshots

        if (

            "requirement" in title_lower

            and

            rule["visual_type"]

            == "Screenshot"

        ):

            score = 0
        # ----------------------------------
        # Save result
        # ----------------------------------

        if score > 0:

            confidence = min(
                score * 20,
                100
            )

            results.append({

                "visual_type":
                rule[
                    "visual_type"
                ],

                "reason":
                rule[
                    "reason"
                ],

                "score":
                score,

                "confidence":
                confidence,

                "evidence":
                evidence

            })

    # ----------------------------------
        # Remove duplicates
        # ----------------------------------

        unique_results = []

        seen = set()

        for result in results:

            visual_type = result["visual_type"]

            if visual_type not in seen:

                seen.add(
                    visual_type
                )

                unique_results.append(
                    result
                )


        # ----------------------------------
        # Remove redundant recommendations
        # ----------------------------------

        visual_types = [

            r["visual_type"]

            for r in unique_results

        ]


        # GIF replaces flowchart
        # for long interactive procedures

        if (

            "GIF Tutorial"

            in visual_types

            and

            step_count >= 6

        ):

            unique_results = [

                r for r in unique_results

                if r["visual_type"]

                != "Flowchart"

            ]


        # Screenshot replaces flowchart
        # for short UI workflows

        if (

            "Screenshot"

            in visual_types

            and

            step_count <= 4

        ):

            unique_results = [

                r for r in unique_results

                if r["visual_type"]

                != "Flowchart"

            ]


        # ----------------------------------
        # Sort results
        # ----------------------------------

        unique_results = sorted(

            unique_results,

            key=lambda x: x["score"],

            reverse=True

        )


        # ----------------------------------
        # Fallback
        # ----------------------------------

        if not unique_results:

            unique_results.append({

                "visual_type":
                "No recommendation",

                "reason":
                "No strong visual opportunity detected",

                "score":0,

                "confidence":0,

                "evidence":[]

            })


        return unique_results[:2]   