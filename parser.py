import re

from normalizer import normalize_line


NODE_PATTERN = re.compile(
    r"Node\s+name\s*:?\s*(.*)",
    re.IGNORECASE
)

TEST_PATTERN = re.compile(
    r"Test\s*'([^']+)'",
    re.IGNORECASE
)

TEST_FALLBACK_PATTERN = re.compile(
    r"Test\s*'(.+)$",
    re.IGNORECASE
)


def extract_node_name(text):
    match = NODE_PATTERN.search(text)

    if not match:
        return None

    name = match.group(1).strip()

    if not name:
        return None

    return name


def extract_test_name(text):
    match = TEST_PATTERN.search(text)

    if match:
        return match.group(1).strip()

    match = TEST_FALLBACK_PATTERN.search(text)

    if match:
        return match.group(1).strip()

    return None


def normalize_node_name(name):
    if name is None:
        return None

    return " ".join(name.lower().split())


def is_flow_node(text, config):
    return config["flow_node_text"].lower() in text.lower()


def build_line_record(line, line_number, current_test, config):
    normalized = normalize_line(line, config)

    test_name = extract_test_name(normalized)

    if test_name is None:
        test_name = extract_test_name(line)

    if test_name:
        current_test = test_name

    display_text = normalized

    if (
        config["add_test_to_flow_node"]
        and current_test
        and is_flow_node(normalized, config)
    ):
        display_text = f"{normalized} [Test: {current_test}]"

    return {
        "line_number": line_number,
        "original": line.rstrip("\r\n"),
        "normalized": normalized,
        "display": display_text,
        "test_name": current_test,
    }, current_test


def split_into_node_blocks(lines, config):
    blocks = []
    current_block = None
    current_test = None
    prefix_lines = []

    for line_number, line in enumerate(lines, start=1):
        record, current_test = build_line_record(
            line,
            line_number,
            current_test,
            config
        )

        node_name = extract_node_name(record["normalized"])

        if node_name is None:
            node_name = extract_node_name(record["original"])

        if node_name is not None:
            if current_block is not None:
                blocks.append(current_block)

            current_block = {
                "node_name": node_name,
                "node_key": normalize_node_name(node_name),
                "start_line": line_number,
                "lines": [record],
            }

            continue

        if current_block is None:
            prefix_lines.append(record)
        else:
            current_block["lines"].append(record)

    if current_block is not None:
        blocks.append(current_block)

    if prefix_lines:
        blocks.insert(
            0,
            {
                "node_name": "__PREAMBLE__",
                "node_key": "__preamble__",
                "start_line": prefix_lines[0]["line_number"],
                "lines": prefix_lines,
            }
        )

    return blocks