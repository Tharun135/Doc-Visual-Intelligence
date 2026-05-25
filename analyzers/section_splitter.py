import re


def split_sections(text):

    sections = []

    seen = set()

    # ------------------------------------
    # Detect headings
    # Supports:
    #
    # # Heading
    # ## Heading
    # ### Heading
    #
    # Requirement
    # Procedure
    # Result
    # ------------------------------------

    pattern = r'^(#{1,6}\s+.+|Requirement[s]?|Procedure|Result[s]?|Purpose|Overview|Introduction)$'

    matches = list(
        re.finditer(
            pattern,
            text,
            re.MULTILINE | re.IGNORECASE
        )
    )

    # ------------------------------------
    # If no sections found
    # ------------------------------------

    if not matches:

        return [{

            "title": "Document",

            "content": text.strip()

        }]


    # ------------------------------------
    # Build sections
    # ------------------------------------

    for i in range(len(matches)):

        title = matches[i].group()

        # Remove markdown symbols

        title = re.sub(
            r'^#+\s*',
            '',
            title
        ).strip()


        start = matches[i].end()

        if i < len(matches)-1:

            end = matches[i+1].start()

        else:

            end = len(text)


        content = text[start:end].strip()


        # Ignore empty sections

        if not content:

            continue


        # Prevent duplicates

        key = (

            title.lower(),

            content.lower()

        )


        if key not in seen:

            seen.add(key)

            sections.append({

                "title": title,

                "content": content

            })


    # ------------------------------------
    # Debug output
    # ------------------------------------

    print("\n========== Sections ==========")

    for section in sections:

        print(
            f"{section['title']}"
        )

    print("==============================\n")


    return sections