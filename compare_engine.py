import sys
import time
import difflib
import re
import html
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

IGNORE_FIRST_COLUMNS = 5
REMOVE_TIMESTAMPS = True
SHOW_SAME = False

KEYWORD_FILE = "keyword.txt"
EXCLUDE_FILE = "exclude.txt"
RULES_IGNORE_CASE = True

NODE_TEXT = "Node name"

TEST_PREFIX = "Test '"
FLOW_NODE_TEXT = "Start flow node"
ADD_TEST_TO_FLOW_NODE = True

COMPRESS_REPEATS = True
MIN_REPEAT_COUNT = 3

CHANGE_THRESHOLD = 0.55
CHANGE_WINDOW = 30
MIN_LENGTH_RATIO = 0.60

MARK_CHANGED_DIFFERENCES = True
DIFFERENCE_MARKER = "^"

PROGRESS_BAR_WIDTH = 30
PROGRESS_UPDATE_SECONDS = 0.15

TXT_OUTPUT = "compare_results.txt"
HTML_OUTPUT = "compare_results.html"


# ==========================================================
# TIMESTAMP
# ==========================================================

TIMESTAMP_PATTERN = re.compile(
    r"\b"
    r"\d{4}-\d{2}-\d{2}"
    r"\s+"
    r"\d{2}:\d{2}:\d{2}"
    r"(?:[,.]\d+)?"
    r"\b"
)


# ==========================================================
# TIME FORMAT
# ==========================================================

def format_time(seconds):

    if seconds < 0:
        seconds = 0

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d}"
        )

    return (
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


# ==========================================================
# PROGRESS
# ==========================================================

class Progress:

    def __init__(
        self,
        total,
        name="Processing"
    ):

        self.total = max(total, 1)
        self.name = name

        self.start_time = time.perf_counter()
        self.last_update = 0


    def update(
        self,
        current,
        force=False
    ):

        current = min(
            current,
            self.total
        )

        now = time.perf_counter()

        if not force:

            if (
                now - self.last_update
                < PROGRESS_UPDATE_SECONDS
            ):
                return

        self.last_update = now

        elapsed = (
            now - self.start_time
        )

        percentage = (
            current / self.total
        )

        filled = int(
            PROGRESS_BAR_WIDTH
            * percentage
        )

        bar = (
            "█" * filled
            +
            "-" * (
                PROGRESS_BAR_WIDTH
                - filled
            )
        )

        speed = (
            current / elapsed
            if elapsed > 0
            else 0
        )

        if speed > 0:

            eta = (
                self.total - current
            ) / speed

            eta_text = format_time(
                eta
            )

        else:

            eta_text = "--:--"

        print(
            f"\r"
            f"{self.name}: "
            f"[{bar}] "
            f"{percentage * 100:6.2f}% "
            f"| {current:,}/{self.total:,} "
            f"| {speed:,.0f} lines/s "
            f"| Elapsed {format_time(elapsed)} "
            f"| ETA {eta_text}",
            end="",
            flush=True
        )


    def finish(self):

        self.update(
            self.total,
            force=True
        )

        print()


# ==========================================================
# CREATE RULE FILES
# ==========================================================

def create_rule_files():

    keyword_path = Path(
        KEYWORD_FILE
    )

    exclude_path = Path(
        EXCLUDE_FILE
    )

    if not keyword_path.exists():

        with open(
            keyword_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write("Start\n")
            file.write("Node name\n")
            file.write("Test '\n")

        print(
            f"Created: {KEYWORD_FILE}"
        )

    if not exclude_path.exists():

        with open(
            exclude_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(
                "# Add unwanted text here.\n"
            )

            file.write(
                "# One rule per line.\n"
            )

        print(
            f"Created: {EXCLUDE_FILE}"
        )


# ==========================================================
# LOAD RULES
# ==========================================================

def load_rules(path):

    rules = []

    if not Path(path).is_file():
        return rules

    with open(
        path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        for line in file:

            rule = line.strip()

            if not rule:
                continue

            if rule.startswith("#"):
                continue

            rules.append(
                rule
            )

    return rules


# ==========================================================
# RULE MATCHING
# ==========================================================

def matches_rule(
    text,
    rules
):

    if not text:
        return False

    if RULES_IGNORE_CASE:

        check_text = text.lower()

        for rule in rules:

            if (
                rule.lower()
                in check_text
            ):
                return True

    else:

        for rule in rules:

            if rule in text:
                return True

    return False


# ==========================================================
# NORMALIZE LINE
# ==========================================================

def normalize_line(line):

    text = line

    if IGNORE_FIRST_COLUMNS > 0:

        parts = text.split()

        if len(parts) > IGNORE_FIRST_COLUMNS:

            text = " ".join(
                parts[
                    IGNORE_FIRST_COLUMNS:
                ]
            )

        else:

            # Do not convert short lines to empty.
            # Keep them so unrelated short lines
            # do not all become identical.
            text = " ".join(parts)

    if REMOVE_TIMESTAMPS:

        text = TIMESTAMP_PATTERN.sub(
            "",
            text
        )

    text = " ".join(
        text.split()
    )

    return text


# ==========================================================
# TEST NAME
# ==========================================================

def extract_test_name(text):

    if not text:
        return None

    match = re.search(
        r"Test\s*'([^']+)'",
        text,
        re.IGNORECASE
    )

    if match:

        return (
            match.group(1).strip()
        )

    match = re.search(
        r"Test\s*'(.+)$",
        text,
        re.IGNORECASE
    )

    if match:

        return (
            match.group(1).strip()
        )

    return None


# ==========================================================
# FLOW NODE
# ==========================================================

def is_flow_node(text):

    if not text:
        return False

    return (
        FLOW_NODE_TEXT.lower()
        in text.lower()
    )


# ==========================================================
# NODE NAME
# ==========================================================

def extract_node_name(text):

    """
    Examples:

    Node name: POWER_TEST
    Node name = POWER_TEST
    Node name POWER_TEST

    Returns:
        POWER_TEST
    """

    if not text:
        return None

    match = re.search(
        r"\bNode\s+name\b\s*[:=]?\s*(.+)$",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    value = (
        match.group(1).strip()
    )

    if not value:
        return None

    return value


# ==========================================================
# READ LOG
# ==========================================================

def read_log(path):

    records = []

    current_test = None

    with open(
        path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):

            original = line.rstrip(
                "\r\n"
            )

            normalized = normalize_line(
                original
            )

            found_test = extract_test_name(
                normalized
            )

            if found_test:

                current_test = (
                    found_test
                )

            node_name = extract_node_name(
                normalized
            )

            records.append({

                "line":
                    line_number,

                "original":
                    original,

                "compare":
                    normalized,

                "test":
                    current_test,

                "node":
                    node_name
            })

    return records


# ==========================================================
# BUILD NODE BLOCKS
# ==========================================================

def build_node_blocks(records):

    """
    Split log into blocks.

    Every Node name starts a new block.

    Lines before first Node name are PREAMBLE.
    """

    blocks = []

    current_block = {

        "node":
            "__PREAMBLE__",

        "display_node":
            "PREAMBLE",

        "start_line":
            1,

        "records":
            []
    }

    occurrence_counter = {}


    for record in records:

        node_name = (
            record["node"]
        )

        if node_name:

            if current_block["records"]:

                current_block["end_line"] = (
                    current_block[
                        "records"
                    ][-1]["line"]
                )

                blocks.append(
                    current_block
                )

            key = (
                node_name.lower()
            )

            occurrence_counter[key] = (
                occurrence_counter.get(
                    key,
                    0
                )
                + 1
            )

            occurrence = (
                occurrence_counter[
                    key
                ]
            )

            current_block = {

                "node":
                    node_name,

                "display_node":
                    node_name,

                "occurrence":
                    occurrence,

                "start_line":
                    record["line"],

                "records":
                    [record]
            }

        else:

            current_block[
                "records"
            ].append(
                record
            )


    if current_block["records"]:

        current_block["end_line"] = (
            current_block[
                "records"
            ][-1]["line"]
        )

        blocks.append(
            current_block
        )


    return blocks


# ==========================================================
# NODE ALIGNMENT KEY
# ==========================================================

def node_alignment_key(block):

    node = block[
        "node"
    ]

    if node == "__PREAMBLE__":
        return "__PREAMBLE__"

    return node.strip().lower()


# ==========================================================
# ALIGN NODE BLOCKS
# ==========================================================

def align_node_blocks(
    blocks_a,
    blocks_b
):

    """
    Important part of the new architecture.

    Compare the sequence of Node names first.

    Example:

    A:
        POWER
        EXTRA
        NETWORK

    B:
        POWER
        NETWORK

    Result:
        POWER   <-> POWER
        EXTRA   <-> missing
        NETWORK <-> NETWORK
    """

    keys_a = [
        node_alignment_key(block)
        for block in blocks_a
    ]

    keys_b = [
        node_alignment_key(block)
        for block in blocks_b
    ]

    matcher = difflib.SequenceMatcher(
        None,
        keys_a,
        keys_b,
        autojunk=False
    )

    aligned = []


    for (
        tag,
        a_start,
        a_end,
        b_start,
        b_end
    ) in matcher.get_opcodes():


        # ==================================================
        # MATCHED NODES
        # ==================================================

        if tag == "equal":

            count = (
                a_end - a_start
            )

            for offset in range(
                count
            ):

                aligned.append({

                    "type":
                        "MATCH",

                    "a":
                        blocks_a[
                            a_start + offset
                        ],

                    "b":
                        blocks_b[
                            b_start + offset
                        ]
                })


        # ==================================================
        # ONLY A
        # ==================================================

        elif tag == "delete":

            for index in range(
                a_start,
                a_end
            ):

                aligned.append({

                    "type":
                        "A_ONLY",

                    "a":
                        blocks_a[index],

                    "b":
                        None
                })


        # ==================================================
        # ONLY B
        # ==================================================

        elif tag == "insert":

            for index in range(
                b_start,
                b_end
            ):

                aligned.append({

                    "type":
                        "B_ONLY",

                    "a":
                        None,

                    "b":
                        blocks_b[index]
                })


        # ==================================================
        # DIFFERENT NODE SEQUENCES
        # ==================================================

        elif tag == "replace":

            old_blocks = (
                blocks_a[
                    a_start:a_end
                ]
            )

            new_blocks = (
                blocks_b[
                    b_start:b_end
                ]
            )

            old_keys = [
                node_alignment_key(x)
                for x in old_blocks
            ]

            new_keys = [
                node_alignment_key(x)
                for x in new_blocks
            ]

            inner_matcher = (
                difflib.SequenceMatcher(
                    None,
                    old_keys,
                    new_keys,
                    autojunk=False
                )
            )

            for (
                inner_tag,
                ia1,
                ia2,
                ib1,
                ib2
            ) in inner_matcher.get_opcodes():


                if inner_tag == "equal":

                    count = (
                        ia2 - ia1
                    )

                    for offset in range(
                        count
                    ):

                        aligned.append({

                            "type":
                                "MATCH",

                            "a":
                                old_blocks[
                                    ia1 + offset
                                ],

                            "b":
                                new_blocks[
                                    ib1 + offset
                                ]
                        })


                elif inner_tag == "delete":

                    for index in range(
                        ia1,
                        ia2
                    ):

                        aligned.append({

                            "type":
                                "A_ONLY",

                            "a":
                                old_blocks[index],

                            "b":
                                None
                        })


                elif inner_tag == "insert":

                    for index in range(
                        ib1,
                        ib2
                    ):

                        aligned.append({

                            "type":
                                "B_ONLY",

                            "a":
                                None,

                            "b":
                                new_blocks[index]
                        })


                elif inner_tag == "replace":

                    for index in range(
                        ia1,
                        ia2
                    ):

                        aligned.append({

                            "type":
                                "A_ONLY",

                            "a":
                                old_blocks[index],

                            "b":
                                None
                        })

                    for index in range(
                        ib1,
                        ib2
                    ):

                        aligned.append({

                            "type":
                                "B_ONLY",

                            "a":
                                None,

                            "b":
                                new_blocks[index]
                        })


    return aligned


# ==========================================================
# LENGTH FILTER
# ==========================================================

def length_is_reasonable(
    line_a,
    line_b
):

    len_a = len(line_a)
    len_b = len(line_b)

    if (
        len_a == 0
        and len_b == 0
    ):
        return True

    if (
        len_a == 0
        or len_b == 0
    ):
        return False

    shorter = min(
        len_a,
        len_b
    )

    longer = max(
        len_a,
        len_b
    )

    return (
        shorter / longer
        >= MIN_LENGTH_RATIO
    )


# ==========================================================
# SIMILARITY
# ==========================================================

def similarity(
    line_a,
    line_b
):

    if line_a == line_b:
        return 1.0

    if not length_is_reasonable(
        line_a,
        line_b
    ):
        return 0.0

    matcher = difflib.SequenceMatcher(
        None,
        line_a,
        line_b,
        autojunk=True
    )

    if (
        matcher.quick_ratio()
        < CHANGE_THRESHOLD
    ):
        return 0.0

    return matcher.ratio()


# ==========================================================
# MAKE RESULT
# ==========================================================

def make_result(
    result_type,
    old_record=None,
    new_record=None,
    similarity_value=None
):

    return {

        "type":
            result_type,

        "old":
            old_record,

        "new":
            new_record,

        "similarity":
            similarity_value
    }


# ==========================================================
# PAIR CHANGED
# ==========================================================

def pair_changed_lines(
    removed,
    added
):

    results = []

    used_added = set()

    removed_count = len(
        removed
    )

    added_count = len(
        added
    )


    if removed_count == 0:

        for item in added:

            results.append(
                make_result(
                    "ADDED",
                    new_record=item
                )
            )

        return results


    if added_count == 0:

        for item in removed:

            results.append(
                make_result(
                    "REMOVED",
                    old_record=item
                )
            )

        return results


    for (
        removed_index,
        old_item
    ) in enumerate(
        removed
    ):

        old_compare = (
            old_item["compare"]
        )

        best_index = None
        best_score = 0.0


        if removed_count <= 1:

            estimated_index = 0

        else:

            position_ratio = (
                removed_index
                /
                (
                    removed_count
                    - 1
                )
            )

            estimated_index = int(
                position_ratio
                *
                max(
                    added_count - 1,
                    0
                )
            )


        candidate_order = []


        for distance in range(
            CHANGE_WINDOW + 1
        ):

            if distance == 0:

                candidates = [
                    estimated_index
                ]

            else:

                candidates = [
                    estimated_index
                    - distance,

                    estimated_index
                    + distance
                ]


            for candidate in candidates:

                if (
                    0 <= candidate < added_count
                    and
                    candidate not in candidate_order
                ):

                    candidate_order.append(
                        candidate
                    )


        for index in candidate_order:

            if index in used_added:
                continue

            new_item = (
                added[index]
            )

            new_compare = (
                new_item["compare"]
            )

            if not length_is_reasonable(
                old_compare,
                new_compare
            ):
                continue

            score = similarity(
                old_compare,
                new_compare
            )

            if score > best_score:

                best_score = score
                best_index = index

            if best_score >= 0.98:
                break


        if (
            best_index is not None
            and
            best_score >= CHANGE_THRESHOLD
        ):

            new_item = (
                added[
                    best_index
                ]
            )

            used_added.add(
                best_index
            )

            results.append(
                make_result(
                    "CHANGED",

                    old_record=
                        old_item,

                    new_record=
                        new_item,

                    similarity_value=
                        best_score
                )
            )

        else:

            results.append(
                make_result(
                    "REMOVED",
                    old_record=old_item
                )
            )


    for (
        index,
        new_item
    ) in enumerate(
        added
    ):

        if index in used_added:
            continue

        results.append(
            make_result(
                "ADDED",
                new_record=new_item
            )
        )


    return results


# ==========================================================
# COMPARE ONE NODE BLOCK
# ==========================================================

def compare_block(
    block_a,
    block_b
):

    records_a = (
        block_a["records"]
    )

    records_b = (
        block_b["records"]
    )

    normalized_a = [
        x["compare"]
        for x in records_a
    ]

    normalized_b = [
        x["compare"]
        for x in records_b
    ]


    matcher = difflib.SequenceMatcher(
        None,
        normalized_a,
        normalized_b,
        autojunk=True
    )


    results = []


    for (
        tag,
        a_start,
        a_end,
        b_start,
        b_end
    ) in matcher.get_opcodes():


        # ==================================================
        # SAME
        # ==================================================

        if tag == "equal":

            count = (
                a_end - a_start
            )

            for offset in range(
                count
            ):

                results.append(
                    make_result(
                        "SAME",

                        old_record=
                            records_a[
                                a_start + offset
                            ],

                        new_record=
                            records_b[
                                b_start + offset
                            ],

                        similarity_value=
                            1.0
                    )
                )


        # ==================================================
        # REMOVED
        # ==================================================

        elif tag == "delete":

            for index in range(
                a_start,
                a_end
            ):

                results.append(
                    make_result(
                        "REMOVED",

                        old_record=
                            records_a[index]
                    )
                )


        # ==================================================
        # ADDED
        # ==================================================

        elif tag == "insert":

            for index in range(
                b_start,
                b_end
            ):

                results.append(
                    make_result(
                        "ADDED",

                        new_record=
                            records_b[index]
                    )
                )


        # ==================================================
        # REPLACE
        # ==================================================

        elif tag == "replace":

            removed = (
                records_a[
                    a_start:a_end
                ]
            )

            added = (
                records_b[
                    b_start:b_end
                ]
            )

            results.extend(
                pair_changed_lines(
                    removed,
                    added
                )
            )


    return results


# ==========================================================
# BUILD FULL COMPARISON
# ==========================================================

def build_comparison(
    aligned_blocks
):

    comparison = []

    progress = Progress(
        len(aligned_blocks),
        "Comparing nodes"
    )


    for index, pair in enumerate(
        aligned_blocks,
        start=1
    ):

        pair_type = (
            pair["type"]
        )


        # ==================================================
        # MATCH
        # ==================================================

        if pair_type == "MATCH":

            block_a = pair["a"]
            block_b = pair["b"]

            line_results = compare_block(
                block_a,
                block_b
            )

            comparison.append({

                "type":
                    "MATCH",

                "a":
                    block_a,

                "b":
                    block_b,

                "results":
                    line_results
            })


        # ==================================================
        # NODE ONLY IN A
        # ==================================================

        elif pair_type == "A_ONLY":

            block_a = pair["a"]

            line_results = [
                make_result(
                    "REMOVED",
                    old_record=record
                )
                for record
                in block_a["records"]
            ]

            comparison.append({

                "type":
                    "A_ONLY",

                "a":
                    block_a,

                "b":
                    None,

                "results":
                    line_results
            })


        # ==================================================
        # NODE ONLY IN B
        # ==================================================

        elif pair_type == "B_ONLY":

            block_b = pair["b"]

            line_results = [
                make_result(
                    "ADDED",
                    new_record=record
                )
                for record
                in block_b["records"]
            ]

            comparison.append({

                "type":
                    "B_ONLY",

                "a":
                    None,

                "b":
                    block_b,

                "results":
                    line_results
            })


        progress.update(
            index
        )


    progress.finish()

    return comparison


# ==========================================================
# RESULT TEXTS
# ==========================================================

def get_result_texts(item):

    texts = []

    old_record = item.get(
        "old"
    )

    new_record = item.get(
        "new"
    )

    if old_record:

        texts.append(
            old_record[
                "compare"
            ]
        )

    if new_record:

        texts.append(
            new_record[
                "compare"
            ]
        )

    return texts


# ==========================================================
# EXCLUDED?
# ==========================================================

def result_is_excluded(
    item,
    exclude_rules
):

    for text in get_result_texts(
        item
    ):

        if matches_rule(
            text,
            exclude_rules
        ):
            return True

    return False


# ==========================================================
# KEYWORD?
# ==========================================================

def result_is_keyword(
    item,
    keyword_rules
):

    for text in get_result_texts(
        item
    ):

        if matches_rule(
            text,
            keyword_rules
        ):
            return True

    return False


# ==========================================================
# DISPLAY TEXT
# ==========================================================

def build_display_text(record):

    if not record:
        return ""

    text = (
        record["compare"]
    )

    test_name = (
        record["test"]
    )

    if (
        ADD_TEST_TO_FLOW_NODE
        and
        is_flow_node(text)
        and
        test_name
    ):

        return (
            f"{text}    "
            f"[Test: {test_name}]"
        )

    return text


# ==========================================================
# DIFFERENCE MARKERS FOR TXT
# ==========================================================

def create_difference_markers(
    old_text,
    new_text
):

    old_marker = [
        " "
    ] * len(old_text)

    new_marker = [
        " "
    ] * len(new_text)


    matcher = difflib.SequenceMatcher(
        None,
        old_text,
        new_text,
        autojunk=False
    )


    for (
        tag,
        old_start,
        old_end,
        new_start,
        new_end
    ) in matcher.get_opcodes():

        if tag == "equal":
            continue

        if tag in (
            "replace",
            "delete"
        ):

            for index in range(
                old_start,
                old_end
            ):

                old_marker[index] = (
                    DIFFERENCE_MARKER
                )

        if tag in (
            "replace",
            "insert"
        ):

            for index in range(
                new_start,
                new_end
            ):

                new_marker[index] = (
                    DIFFERENCE_MARKER
                )


    return (
        "".join(
            old_marker
        ).rstrip(),

        "".join(
            new_marker
        ).rstrip()
    )


# ==========================================================
# HTML CHARACTER DIFFERENCES
# ==========================================================

def html_diff_pair(
    old_text,
    new_text
):

    matcher = difflib.SequenceMatcher(
        None,
        old_text,
        new_text,
        autojunk=False
    )

    old_parts = []
    new_parts = []


    for (
        tag,
        old_start,
        old_end,
        new_start,
        new_end
    ) in matcher.get_opcodes():

        old_piece = html.escape(
            old_text[
                old_start:old_end
            ]
        )

        new_piece = html.escape(
            new_text[
                new_start:new_end
            ]
        )


        if tag == "equal":

            old_parts.append(
                old_piece
            )

            new_parts.append(
                new_piece
            )

        else:

            if old_piece:

                old_parts.append(
                    '<span class="changed">'
                    + old_piece
                    + '</span>'
                )

            if new_piece:

                new_parts.append(
                    '<span class="changed">'
                    + new_piece
                    + '</span>'
                )


    return (
        "".join(old_parts),
        "".join(new_parts)
    )


# ==========================================================
# TXT REPORT
# ==========================================================

def write_txt_report(
    comparison,
    file_a,
    file_b,
    keyword_rules,
    exclude_rules
):

    name_a = Path(
        file_a
    ).name

    name_b = Path(
        file_b
    ).name


    with open(
        TXT_OUTPUT,
        "w",
        encoding="utf-8"
    ) as output:


        for section in comparison:

            section_type = (
                section["type"]
            )

            block_a = section["a"]
            block_b = section["b"]


            # ==============================================
            # NODE HEADER
            # ==============================================

            output.write(
                "\n"
                + "=" * 100
                + "\n"
            )


            if section_type == "MATCH":

                node_name = (
                    block_a[
                        "display_node"
                    ]
                )

                output.write(
                    f"NODE: {node_name}\n"
                )

                output.write(
                    f"{name_a}: "
                    f"{block_a['start_line']}"
                    f"-"
                    f"{block_a['end_line']}\n"
                )

                output.write(
                    f"{name_b}: "
                    f"{block_b['start_line']}"
                    f"-"
                    f"{block_b['end_line']}\n"
                )


            elif section_type == "A_ONLY":

                node_name = (
                    block_a[
                        "display_node"
                    ]
                )

                output.write(
                    f"NODE ONLY IN "
                    f"{name_a}: "
                    f"{node_name}\n"
                )


            elif section_type == "B_ONLY":

                node_name = (
                    block_b[
                        "display_node"
                    ]
                )

                output.write(
                    f"NODE ONLY IN "
                    f"{name_b}: "
                    f"{node_name}\n"
                )


            output.write(
                "=" * 100
                + "\n\n"
            )


            # ==============================================
            # LINES
            # ==============================================

            for item in section[
                "results"
            ]:

                if result_is_excluded(
                    item,
                    exclude_rules
                ):
                    continue


                item_type = (
                    item["type"]
                )

                is_keyword = (
                    result_is_keyword(
                        item,
                        keyword_rules
                    )
                )


                # ==========================================
                # SAME
                # ==========================================

                if item_type == "SAME":

                    if not (
                        SHOW_SAME
                        or is_keyword
                    ):
                        continue


                    old_record = (
                        item["old"]
                    )

                    new_record = (
                        item["new"]
                    )


                    old_display = (
                        build_display_text(
                            old_record
                        )
                    )

                    new_display = (
                        build_display_text(
                            new_record
                        )
                    )


                    if is_keyword:

                        output.write(
                            "[KEYWORD]\n"
                        )

                    else:

                        output.write(
                            "[SAME]\n"
                        )


                    if (
                        old_display
                        == new_display
                    ):

                        output.write(
                            f"{name_a}:"
                            f"{old_record['line']} "
                            f"| "
                            f"{name_b}:"
                            f"{new_record['line']} "
                            f"{old_display}\n\n"
                        )

                    else:

                        output.write(
                            f"{name_a}:"
                            f"{old_record['line']} "
                            f"{old_display}\n"
                        )

                        output.write(
                            f"{name_b}:"
                            f"{new_record['line']} "
                            f"{new_display}\n\n"
                        )


                # ==========================================
                # CHANGED
                # ==========================================

                elif item_type == "CHANGED":

                    old_record = (
                        item["old"]
                    )

                    new_record = (
                        item["new"]
                    )

                    old_text = (
                        build_display_text(
                            old_record
                        )
                    )

                    new_text = (
                        build_display_text(
                            new_record
                        )
                    )

                    percent = (
                        item[
                            "similarity"
                        ]
                        * 100
                    )


                    output.write(
                        f"[CHANGED] "
                        f"Similarity: "
                        f"{percent:.1f}%\n"
                    )


                    old_prefix = (
                        f"{name_a}:"
                        f"{old_record['line']} "
                        f"< "
                    )

                    new_prefix = (
                        f"{name_b}:"
                        f"{new_record['line']} "
                        f"> "
                    )


                    output.write(
                        old_prefix
                        + old_text
                        + "\n"
                    )


                    old_marker = ""
                    new_marker = ""


                    if MARK_CHANGED_DIFFERENCES:

                        (
                            old_marker,
                            new_marker
                        ) = (
                            create_difference_markers(
                                old_text,
                                new_text
                            )
                        )


                    if old_marker:

                        output.write(
                            " " * len(
                                old_prefix
                            )
                            +
                            old_marker
                            +
                            "\n"
                        )


                    output.write(
                        new_prefix
                        + new_text
                        + "\n"
                    )


                    if new_marker:

                        output.write(
                            " " * len(
                                new_prefix
                            )
                            +
                            new_marker
                            +
                            "\n"
                        )


                    output.write(
                        "\n"
                    )


                # ==========================================
                # REMOVED
                # ==========================================

                elif item_type == "REMOVED":

                    record = (
                        item["old"]
                    )

                    display = (
                        build_display_text(
                            record
                        )
                    )

                    output.write(
                        "[REMOVED]\n"
                    )

                    output.write(
                        f"{name_a}:"
                        f"{record['line']} "
                        f"< "
                        f"{display}\n\n"
                    )


                # ==========================================
                # ADDED
                # ==========================================

                elif item_type == "ADDED":

                    record = (
                        item["new"]
                    )

                    display = (
                        build_display_text(
                            record
                        )
                    )

                    output.write(
                        "[ADDED]\n"
                    )

                    output.write(
                        f"{name_b}:"
                        f"{record['line']} "
                        f"> "
                        f"{display}\n\n"
                    )


# ==========================================================
# HTML REPORT
# ==========================================================

def write_html_report(
    comparison,
    file_a,
    file_b,
    keyword_rules,
    exclude_rules
):

    name_a = Path(
        file_a
    ).name

    name_b = Path(
        file_b
    ).name


    with open(
        HTML_OUTPUT,
        "w",
        encoding="utf-8"
    ) as output:


        output.write(
            """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Log Comparison</title>

<style>

body {
    font-family: Consolas, "Courier New", monospace;
    background: #111;
    color: #ddd;
    margin: 20px;
}

h1 {
    color: white;
}

.node {
    margin-top: 30px;
    margin-bottom: 30px;
    border: 1px solid #444;
    border-radius: 8px;
    overflow: hidden;
}

.node-header {
    background: #252525;
    padding: 12px;
    font-size: 18px;
    font-weight: bold;
}

.node-info {
    background: #191919;
    padding: 8px 12px;
    color: #aaa;
}

.entry {
    padding: 8px 12px;
    border-top: 1px solid #292929;
    white-space: pre-wrap;
    word-break: break-word;
}

.label {
    font-weight: bold;
}

.changed {
    color: #ff4d4d;
    background: rgba(255, 0, 0, 0.18);
    font-weight: bold;
    text-decoration: underline;
}

.added {
    color: #7CFC8A;
}

.removed {
    color: #ff8080;
}

.keyword {
    color: #ffd966;
}

.filename {
    color: #7db7ff;
    font-weight: bold;
}

.missing-node {
    color: #ff8080;
    font-weight: bold;
}

.similarity {
    color: #aaa;
}

</style>

</head>

<body>

<h1>Log Comparison</h1>
"""
        )


        output.write(
            "<div>"
            f"<b>A:</b> {html.escape(name_a)}"
            "<br>"
            f"<b>B:</b> {html.escape(name_b)}"
            "</div>"
        )


        for section in comparison:

            section_type = (
                section["type"]
            )

            block_a = section["a"]
            block_b = section["b"]


            output.write(
                '<div class="node">'
            )


            # ==============================================
            # NODE HEADER
            # ==============================================

            if section_type == "MATCH":

                node_name = (
                    block_a[
                        "display_node"
                    ]
                )

                output.write(
                    '<div class="node-header">'
                    f'NODE: {html.escape(node_name)}'
                    '</div>'
                )

                output.write(
                    '<div class="node-info">'
                    f'{html.escape(name_a)}: '
                    f'{block_a["start_line"]}'
                    '-'
                    f'{block_a["end_line"]}'
                    '<br>'
                    f'{html.escape(name_b)}: '
                    f'{block_b["start_line"]}'
                    '-'
                    f'{block_b["end_line"]}'
                    '</div>'
                )


            elif section_type == "A_ONLY":

                node_name = (
                    block_a[
                        "display_node"
                    ]
                )

                output.write(
                    '<div class="node-header '
                    'missing-node">'
                    f'NODE ONLY IN '
                    f'{html.escape(name_a)}: '
                    f'{html.escape(node_name)}'
                    '</div>'
                )


            elif section_type == "B_ONLY":

                node_name = (
                    block_b[
                        "display_node"
                    ]
                )

                output.write(
                    '<div class="node-header '
                    'missing-node">'
                    f'NODE ONLY IN '
                    f'{html.escape(name_b)}: '
                    f'{html.escape(node_name)}'
                    '</div>'
                )


            # ==============================================
            # RESULTS
            # ==============================================

            for item in section[
                "results"
            ]:

                if result_is_excluded(
                    item,
                    exclude_rules
                ):
                    continue


                item_type = (
                    item["type"]
                )

                is_keyword = (
                    result_is_keyword(
                        item,
                        keyword_rules
                    )
                )


                # ==========================================
                # SAME
                # ==========================================

                if item_type == "SAME":

                    if not (
                        SHOW_SAME
                        or is_keyword
                    ):
                        continue


                    old_record = (
                        item["old"]
                    )

                    new_record = (
                        item["new"]
                    )

                    display = (
                        build_display_text(
                            old_record
                        )
                    )

                    css_class = (
                        "keyword"
                        if is_keyword
                        else ""
                    )

                    label = (
                        "KEYWORD"
                        if is_keyword
                        else "SAME"
                    )


                    output.write(
                        f'<div class="entry {css_class}">'
                        f'<span class="label">'
                        f'[{label}]'
                        f'</span><br>'
                        f'<span class="filename">'
                        f'{html.escape(name_a)}:'
                        f'{old_record["line"]}'
                        f'</span>'
                        f' | '
                        f'<span class="filename">'
                        f'{html.escape(name_b)}:'
                        f'{new_record["line"]}'
                        f'</span> '
                        f'{html.escape(display)}'
                        f'</div>'
                    )


                # ==========================================
                # CHANGED
                # ==========================================

                elif item_type == "CHANGED":

                    old_record = (
                        item["old"]
                    )

                    new_record = (
                        item["new"]
                    )

                    old_text = (
                        build_display_text(
                            old_record
                        )
                    )

                    new_text = (
                        build_display_text(
                            new_record
                        )
                    )


                    (
                        old_html,
                        new_html
                    ) = html_diff_pair(
                        old_text,
                        new_text
                    )


                    percent = (
                        item[
                            "similarity"
                        ]
                        * 100
                    )


                    output.write(
                        '<div class="entry">'
                        '<span class="label">'
                        '[CHANGED]'
                        '</span> '
                        '<span class="similarity">'
                        f'Similarity: {percent:.1f}%'
                        '</span>'
                        '<br>'
                        '<span class="filename">'
                        f'{html.escape(name_a)}:'
                        f'{old_record["line"]}'
                        '</span> '
                        '&lt; '
                        f'{old_html}'
                        '<br>'
                        '<span class="filename">'
                        f'{html.escape(name_b)}:'
                        f'{new_record["line"]}'
                        '</span> '
                        '&gt; '
                        f'{new_html}'
                        '</div>'
                    )


                # ==========================================
                # REMOVED
                # ==========================================

                elif item_type == "REMOVED":

                    record = (
                        item["old"]
                    )

                    display = (
                        build_display_text(
                            record
                        )
                    )


                    output.write(
                        '<div class="entry removed">'
                        '<span class="label">'
                        '[REMOVED]'
                        '</span><br>'
                        '<span class="filename">'
                        f'{html.escape(name_a)}:'
                        f'{record["line"]}'
                        '</span> '
                        '&lt; '
                        f'{html.escape(display)}'
                        '</div>'
                    )


                # ==========================================
                # ADDED
                # ==========================================

                elif item_type == "ADDED":

                    record = (
                        item["new"]
                    )

                    display = (
                        build_display_text(
                            record
                        )
                    )


                    output.write(
                        '<div class="entry added">'
                        '<span class="label">'
                        '[ADDED]'
                        '</span><br>'
                        '<span class="filename">'
                        f'{html.escape(name_b)}:'
                        f'{record["line"]}'
                        '</span> '
                        '&gt; '
                        f'{html.escape(display)}'
                        '</div>'
                    )


            output.write(
                '</div>'
            )


        output.write(
            """
</body>
</html>
"""
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    if len(sys.argv) != 3:

        print()

        print(
            "Usage:"
        )

        print(
            "python.exe compare_engine.py "
            "file_A.log file_B.log"
        )

        print()

        sys.exit(1)


    file_a = sys.argv[1]
    file_b = sys.argv[2]


    if not Path(file_a).is_file():

        print(
            f"File not found: "
            f"{file_a}"
        )

        sys.exit(1)


    if not Path(file_b).is_file():

        print(
            f"File not found: "
            f"{file_b}"
        )

        sys.exit(1)


    total_start = (
        time.perf_counter()
    )


    # ======================================================
    # RULE FILES
    # ======================================================

    create_rule_files()


    keyword_rules = load_rules(
        KEYWORD_FILE
    )

    exclude_rules = load_rules(
        EXCLUDE_FILE
    )


    print()

    print(
        f"Keywords loaded: "
        f"{len(keyword_rules):,}"
    )

    print(
        f"Excludes loaded: "
        f"{len(exclude_rules):,}"
    )


    # ======================================================
    # READ LOGS
    # ======================================================

    print()

    print(
        f"Reading A: "
        f"{file_a}"
    )

    records_a = read_log(
        file_a
    )

    print(
        f"Lines A: "
        f"{len(records_a):,}"
    )


    print()

    print(
        f"Reading B: "
        f"{file_b}"
    )

    records_b = read_log(
        file_b
    )

    print(
        f"Lines B: "
        f"{len(records_b):,}"
    )


    # ======================================================
    # BUILD NODE BLOCKS
    # ======================================================

    print()

    print(
        "Finding Node name blocks..."
    )


    blocks_a = build_node_blocks(
        records_a
    )

    blocks_b = build_node_blocks(
        records_b
    )


    print(
        f"Node blocks A: "
        f"{len(blocks_a):,}"
    )

    print(
        f"Node blocks B: "
        f"{len(blocks_b):,}"
    )


    # ======================================================
    # ALIGN NODES
    # ======================================================

    print()

    print(
        "Aligning Node name blocks..."
    )


    aligned_blocks = (
        align_node_blocks(
            blocks_a,
            blocks_b
        )
    )


    matched_nodes = sum(
        1
        for x in aligned_blocks
        if x["type"] == "MATCH"
    )

    only_a = sum(
        1
        for x in aligned_blocks
        if x["type"] == "A_ONLY"
    )

    only_b = sum(
        1
        for x in aligned_blocks
        if x["type"] == "B_ONLY"
    )


    print(
        f"Matched nodes: "
        f"{matched_nodes:,}"
    )

    print(
        f"Only in A:     "
        f"{only_a:,}"
    )

    print(
        f"Only in B:     "
        f"{only_b:,}"
    )


    # ======================================================
    # COMPARE EACH MATCHED NODE
    # ======================================================

    print()

    comparison = build_comparison(
        aligned_blocks
    )


    # ======================================================
    # TXT
    # ======================================================

    print()

    print(
        f"Writing TXT: "
        f"{TXT_OUTPUT}"
    )


    write_txt_report(
        comparison,
        file_a,
        file_b,
        keyword_rules,
        exclude_rules
    )


    # ======================================================
    # HTML
    # ======================================================

    print(
        f"Writing HTML: "
        f"{HTML_OUTPUT}"
    )


    write_html_report(
        comparison,
        file_a,
        file_b,
        keyword_rules,
        exclude_rules
    )


    # ======================================================
    # COMPLETE
    # ======================================================

    total_elapsed = (
        time.perf_counter()
        - total_start
    )


    print()

    print(
        "=" * 70
    )

    print(
        "COMPARISON COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"Lines A:       "
        f"{len(records_a):,}"
    )

    print(
        f"Lines B:       "
        f"{len(records_b):,}"
    )

    print(
        f"Node blocks A: "
        f"{len(blocks_a):,}"
    )

    print(
        f"Node blocks B: "
        f"{len(blocks_b):,}"
    )

    print(
        f"Matched nodes: "
        f"{matched_nodes:,}"
    )

    print(
        f"Only in A:     "
        f"{only_a:,}"
    )

    print(
        f"Only in B:     "
        f"{only_b:,}"
    )

    print(
        "-" * 70
    )

    print(
        f"TXT report:    "
        f"{TXT_OUTPUT}"
    )

    print(
        f"HTML report:   "
        f"{HTML_OUTPUT}"
    )

    print(
        f"Keywords:      "
        f"{KEYWORD_FILE}"
    )

    print(
        f"Excludes:      "
        f"{EXCLUDE_FILE}"
    )

    print(
        f"Total time:    "
        f"{format_time(total_elapsed)}"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":

    main()