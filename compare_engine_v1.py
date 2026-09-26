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

TEXT_REPORT = "compare_results.txt"
HTML_REPORT = "compare_results.html"

RULES_IGNORE_CASE = True

COMPRESS_REPEATS = True
MIN_REPEAT_COUNT = 3

CHANGE_THRESHOLD = 0.55
CHANGE_WINDOW = 30
MIN_LENGTH_RATIO = 0.60

MARK_CHANGED_DIFFERENCES = True
DIFFERENCE_MARKER = "^"

PROGRESS_BAR_WIDTH = 30
PROGRESS_UPDATE_SECONDS = 0.15


# ==========================================================
# NODE SETTINGS
# ==========================================================

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

FLOW_NODE_TEXT = "Start flow node"

ADD_TEST_TO_FLOW_NODE = True


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
# TIME
# ==========================================================

def format_time(seconds):

    seconds = max(
        int(seconds),
        0
    )

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

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

        self.total = max(
            total,
            1
        )

        self.name = name

        self.start_time = (
            time.perf_counter()
        )

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

        now = (
            time.perf_counter()
        )

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

            eta_text = (
                format_time(eta)
            )

        else:

            eta_text = "--:--"

        print(
            f"\r{self.name}: "
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
# RULE FILES
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
                "# Add unwanted text here\n"
            )

            file.write(
                "# One rule per line\n"
            )

        print(
            f"Created: {EXCLUDE_FILE}"
        )


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

            rule = (
                line.strip()
            )

            if not rule:
                continue

            if rule.startswith("#"):
                continue

            rules.append(
                rule
            )

    return rules


def matches_rule(
    text,
    rules
):

    if not text:
        return False

    if RULES_IGNORE_CASE:

        check_text = (
            text.lower()
        )

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
# NORMALIZATION
# ==========================================================

def normalize_line(line):

    text = line

    if IGNORE_FIRST_COLUMNS > 0:

        parts = (
            text.split()
        )

        if (
            len(parts)
            <= IGNORE_FIRST_COLUMNS
        ):

            text = ""

        else:

            text = " ".join(
                parts[
                    IGNORE_FIRST_COLUMNS:
                ]
            )


    if REMOVE_TIMESTAMPS:

        text = (
            TIMESTAMP_PATTERN.sub(
                "",
                text
            )
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


    match = (
        TEST_PATTERN.search(
            text
        )
    )

    if match:

        return (
            match.group(1).strip()
        )


    match = (
        TEST_FALLBACK_PATTERN.search(
            text
        )
    )

    if match:

        return (
            match.group(1).strip()
        )


    return None


# ==========================================================
# NODE NAME
# ==========================================================

def extract_node_name(text):

    if not text:
        return None


    match = (
        NODE_PATTERN.search(
            text
        )
    )

    if not match:
        return None


    node_name = (
        match.group(1).strip()
    )


    if not node_name:

        return None


    return node_name


def normalize_node_name(name):

    if not name:
        return ""

    return (
        " ".join(
            name.split()
        ).lower()
    )


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


def build_display_text(
    text,
    test_name
):

    if not text:
        return text


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
# READ LOG
# ==========================================================

def read_file(path):

    lines = []

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

            original = (
                line.rstrip(
                    "\r\n"
                )
            )

            normalized = (
                normalize_line(
                    original
                )
            )


            # Use both versions for structural detection.
            # This prevents metadata stripping from hiding
            # Test / Node name.
            found_test = (
                extract_test_name(
                    normalized
                )
                or
                extract_test_name(
                    original
                )
            )


            if found_test:

                current_test = (
                    found_test
                )


            node_name = (
                extract_node_name(
                    normalized
                )
                or
                extract_node_name(
                    original
                )
            )


            lines.append({

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


    return lines


# ==========================================================
# SPLIT INTO NODE BLOCKS
# ==========================================================

def split_into_node_blocks(lines):

    blocks = []

    current_block = None

    preamble = []


    for item in lines:

        node_name = (
            item["node"]
        )


        if node_name:

            if current_block is not None:

                blocks.append(
                    current_block
                )

            current_block = {

                "node_name":
                    node_name,

                "node_key":
                    normalize_node_name(
                        node_name
                    ),

                "node_line":
                    item["line"],

                "lines": [
                    item
                ]
            }


        else:

            if current_block is None:

                preamble.append(
                    item
                )

            else:

                current_block[
                    "lines"
                ].append(
                    item
                )


    if current_block is not None:

        blocks.append(
            current_block
        )


    return (
        preamble,
        blocks
    )


# ==========================================================
# ALIGN NODE BLOCKS
# ==========================================================

def align_node_blocks(
    blocks_a,
    blocks_b
):

    keys_a = [
        block["node_key"]
        for block in blocks_a
    ]

    keys_b = [
        block["node_key"]
        for block in blocks_b
    ]


    matcher = (
        difflib.SequenceMatcher(
            None,
            keys_a,
            keys_b,
            autojunk=False
        )
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
        # EXACTLY ALIGNED NODE SEQUENCE
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
        # NODE ONLY IN A
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
                        blocks_a[
                            index
                        ],

                    "b":
                        None
                })


        # ==================================================
        # NODE ONLY IN B
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
                        blocks_b[
                            index
                        ]
                })


        # ==================================================
        # REPLACE
        # ==================================================

        elif tag == "replace":

            sub_a = (
                blocks_a[
                    a_start:a_end
                ]
            )

            sub_b = (
                blocks_b[
                    b_start:b_end
                ]
            )


            # Try to find matching node names inside
            # this replaced region.
            used_b = set()


            for block_a in sub_a:

                found_index = None


                for index_b, block_b in enumerate(
                    sub_b
                ):

                    if index_b in used_b:
                        continue


                    if (
                        block_a["node_key"]
                        ==
                        block_b["node_key"]
                    ):

                        found_index = (
                            index_b
                        )

                        break


                if found_index is not None:

                    used_b.add(
                        found_index
                    )

                    aligned.append({

                        "type":
                            "MATCH",

                        "a":
                            block_a,

                        "b":
                            sub_b[
                                found_index
                            ]
                    })


                else:

                    aligned.append({

                        "type":
                            "A_ONLY",

                        "a":
                            block_a,

                        "b":
                            None
                    })


            for index_b, block_b in enumerate(
                sub_b
            ):

                if index_b in used_b:
                    continue


                aligned.append({

                    "type":
                        "B_ONLY",

                    "a":
                        None,

                    "b":
                        block_b
                })


    return aligned


# ==========================================================
# LENGTH CHECK
# ==========================================================

def length_is_reasonable(
    line_a,
    line_b
):

    len_a = len(
        line_a
    )

    len_b = len(
        line_b
    )


    if (
        len_a == 0
        and
        len_b == 0
    ):

        return True


    if (
        len_a == 0
        or
        len_b == 0
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


    matcher = (
        difflib.SequenceMatcher(
            None,
            line_a,
            line_b,
            autojunk=True
        )
    )


    if (
        matcher.quick_ratio()
        < CHANGE_THRESHOLD
    ):

        return 0.0


    return (
        matcher.ratio()
    )


# ==========================================================
# RESULT
# ==========================================================

def make_result(
    result_type,
    old_item=None,
    new_item=None,
    similarity_value=None
):

    return {

        "type":
            result_type,

        "old":
            old_item,

        "new":
            new_item,

        "similarity":
            similarity_value
    }


# ==========================================================
# PAIR CHANGED LINES
# ==========================================================

def pair_changed_lines(
    removed,
    added
):

    results = []

    used_added = set()


    if not removed:

        for item in added:

            results.append(
                make_result(
                    "ADDED",
                    new_item=item
                )
            )

        return results


    if not added:

        for item in removed:

            results.append(
                make_result(
                    "REMOVED",
                    old_item=item
                )
            )

        return results


    removed_count = len(
        removed
    )

    added_count = len(
        added
    )


    for (
        removed_index,
        old_item
    ) in enumerate(
        removed
    ):

        best_index = None

        best_score = 0.0


        if removed_count <= 1:

            estimated_index = 0

        else:

            position_ratio = (
                removed_index
                /
                (
                    removed_count - 1
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


        candidates = []


        for distance in range(
            CHANGE_WINDOW + 1
        ):

            positions = (
                [estimated_index]
                if distance == 0
                else [
                    estimated_index - distance,
                    estimated_index + distance
                ]
            )


            for candidate in positions:

                if (
                    0 <= candidate < added_count
                    and
                    candidate not in candidates
                ):

                    candidates.append(
                        candidate
                    )


        for candidate in candidates:

            if candidate in used_added:
                continue


            new_item = (
                added[candidate]
            )


            score = similarity(
                old_item["compare"],
                new_item["compare"]
            )


            if score > best_score:

                best_score = score

                best_index = (
                    candidate
                )


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
                    old_item,
                    new_item,
                    best_score
                )
            )


        else:

            results.append(
                make_result(
                    "REMOVED",
                    old_item=old_item
                )
            )


    for index, item in enumerate(
        added
    ):

        if index not in used_added:

            results.append(
                make_result(
                    "ADDED",
                    new_item=item
                )
            )


    return results


# ==========================================================
# COMPARE LINE LISTS
# ==========================================================

def compare_line_lists(
    lines_a,
    lines_b
):

    compare_a = [
        item["compare"]
        for item in lines_a
    ]

    compare_b = [
        item["compare"]
        for item in lines_b
    ]


    matcher = (
        difflib.SequenceMatcher(
            None,
            compare_a,
            compare_b,
            autojunk=True
        )
    )


    results = []


    for (
        tag,
        a_start,
        a_end,
        b_start,
        b_end
    ) in matcher.get_opcodes():


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

                        lines_a[
                            a_start + offset
                        ],

                        lines_b[
                            b_start + offset
                        ],

                        1.0
                    )
                )


        elif tag == "delete":

            for index in range(
                a_start,
                a_end
            ):

                results.append(
                    make_result(
                        "REMOVED",
                        old_item=
                            lines_a[index]
                    )
                )


        elif tag == "insert":

            for index in range(
                b_start,
                b_end
            ):

                results.append(
                    make_result(
                        "ADDED",
                        new_item=
                            lines_b[index]
                    )
                )


        elif tag == "replace":

            results.extend(
                pair_changed_lines(

                    lines_a[
                        a_start:a_end
                    ],

                    lines_b[
                        b_start:b_end
                    ]
                )
            )


    return results


# ==========================================================
# KEYWORD / EXCLUDE
# ==========================================================

def result_texts(item):

    texts = []


    if item.get("old"):

        texts.append(
            item["old"]["compare"]
        )

        texts.append(
            item["old"]["original"]
        )


    if item.get("new"):

        texts.append(
            item["new"]["compare"]
        )

        texts.append(
            item["new"]["original"]
        )


    return texts


def result_matches_rules(
    item,
    rules
):

    for text in result_texts(
        item
    ):

        if matches_rule(
            text,
            rules
        ):

            return True


    return False


def filter_results(
    results,
    exclude_rules
):

    filtered = []


    for item in results:

        if result_matches_rules(
            item,
            exclude_rules
        ):

            continue


        filtered.append(
            item
        )


    return filtered


# ==========================================================
# DIFFERENCE MARKERS TXT
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


    matcher = (
        difflib.SequenceMatcher(
            None,
            old_text,
            new_text,
            autojunk=False
        )
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
# HTML CHARACTER DIFF
# ==========================================================

def html_diff(
    old_text,
    new_text
):

    matcher = (
        difflib.SequenceMatcher(
            None,
            old_text,
            new_text,
            autojunk=False
        )
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


        old_part = (
            old_text[
                old_start:old_end
            ]
        )

        new_part = (
            new_text[
                new_start:new_end
            ]
        )


        if tag == "equal":

            old_parts.append(
                html.escape(
                    old_part
                )
            )

            new_parts.append(
                html.escape(
                    new_part
                )
            )


        else:

            if old_part:

                old_parts.append(
                    '<span class="difference">'
                    +
                    html.escape(
                        old_part
                    )
                    +
                    '</span>'
                )


            if new_part:

                new_parts.append(
                    '<span class="difference">'
                    +
                    html.escape(
                        new_part
                    )
                    +
                    '</span>'
                )


    return (
        "".join(old_parts),
        "".join(new_parts)
    )


# ==========================================================
# NODE LABEL
# ==========================================================

def node_title(
    aligned_item
):

    block_a = (
        aligned_item["a"]
    )

    block_b = (
        aligned_item["b"]
    )


    if block_a:

        return (
            block_a["node_name"]
        )


    if block_b:

        return (
            block_b["node_name"]
        )


    return "UNKNOWN"


# ==========================================================
# BUILD ALL COMPARISONS
# ==========================================================

def build_comparisons(
    preamble_a,
    blocks_a,
    preamble_b,
    blocks_b,
    exclude_rules
):

    comparisons = []


    # ======================================================
    # PREAMBLE
    # ======================================================

    if (
        preamble_a
        or preamble_b
    ):

        preamble_results = (
            compare_line_lists(
                preamble_a,
                preamble_b
            )
        )

        preamble_results = (
            filter_results(
                preamble_results,
                exclude_rules
            )
        )


        comparisons.append({

            "kind":
                "PREAMBLE",

            "node":
                "BEFORE FIRST NODE",

            "a":
                None,

            "b":
                None,

            "results":
                preamble_results
        })


    # ======================================================
    # ALIGN NODES
    # ======================================================

    aligned = (
        align_node_blocks(
            blocks_a,
            blocks_b
        )
    )


    for item in aligned:

        kind = (
            item["type"]
        )

        block_a = (
            item["a"]
        )

        block_b = (
            item["b"]
        )


        # ==================================================
        # MATCHED NODE
        # ==================================================

        if kind == "MATCH":

            results = (
                compare_line_lists(
                    block_a["lines"],
                    block_b["lines"]
                )
            )


        # ==================================================
        # ONLY A
        # ==================================================

        elif kind == "A_ONLY":

            results = [

                make_result(
                    "REMOVED",
                    old_item=line
                )

                for line in (
                    block_a["lines"]
                )
            ]


        # ==================================================
        # ONLY B
        # ==================================================

        else:

            results = [

                make_result(
                    "ADDED",
                    new_item=line
                )

                for line in (
                    block_b["lines"]
                )
            ]


        results = (
            filter_results(
                results,
                exclude_rules
            )
        )


        comparisons.append({

            "kind":
                kind,

            "node":
                node_title(
                    item
                ),

            "a":
                block_a,

            "b":
                block_b,

            "results":
                results
        })


    return comparisons


# ==========================================================
# SHOULD DISPLAY
# ==========================================================

def should_display(
    result,
    keyword_rules
):

    if result["type"] != "SAME":

        return True


    if SHOW_SAME:

        return True


    return (
        result_matches_rules(
            result,
            keyword_rules
        )
    )


# ==========================================================
# TXT REPORT
# ==========================================================

def write_text_report(
    comparisons,
    file_a,
    file_b,
    keyword_rules
):

    name_a = (
        Path(file_a).name
    )

    name_b = (
        Path(file_b).name
    )


    with open(
        TEXT_REPORT,
        "w",
        encoding="utf-8"
    ) as output:


        for comparison in comparisons:

            node = (
                comparison["node"]
            )

            kind = (
                comparison["kind"]
            )


            output.write(
                "\n"
                +
                "=" * 100
                +
                "\n"
            )


            if kind == "MATCH":

                output.write(
                    f"NODE: {node}\n"
                )


            elif kind == "A_ONLY":

                output.write(
                    f"NODE ONLY IN "
                    f"{name_a}: "
                    f"{node}\n"
                )


            elif kind == "B_ONLY":

                output.write(
                    f"NODE ONLY IN "
                    f"{name_b}: "
                    f"{node}\n"
                )


            else:

                output.write(
                    f"{node}\n"
                )


            output.write(
                "=" * 100
                +
                "\n\n"
            )


            for result in (
                comparison["results"]
            ):


                if not should_display(
                    result,
                    keyword_rules
                ):

                    continue


                result_type = (
                    result["type"]
                )


                # ==========================================
                # SAME
                # ==========================================

                if result_type == "SAME":

                    old = (
                        result["old"]
                    )

                    new = (
                        result["new"]
                    )


                    display_old = (
                        build_display_text(
                            old["compare"],
                            old["test"]
                        )
                    )

                    display_new = (
                        build_display_text(
                            new["compare"],
                            new["test"]
                        )
                    )


                    output.write(
                        "[KEYWORD]\n"
                        if not SHOW_SAME
                        else
                        "[SAME]\n"
                    )


                    if (
                        display_old
                        == display_new
                    ):

                        output.write(
                            f"{name_a}:{old['line']} "
                            f"| "
                            f"{name_b}:{new['line']} "
                            f"{display_old}\n\n"
                        )

                    else:

                        output.write(
                            f"{name_a}:{old['line']} "
                            f"{display_old}\n"
                        )

                        output.write(
                            f"{name_b}:{new['line']} "
                            f"{display_new}\n\n"
                        )


                # ==========================================
                # CHANGED
                # ==========================================

                elif (
                    result_type
                    == "CHANGED"
                ):

                    old = (
                        result["old"]
                    )

                    new = (
                        result["new"]
                    )


                    old_text = (
                        build_display_text(
                            old["compare"],
                            old["test"]
                        )
                    )

                    new_text = (
                        build_display_text(
                            new["compare"],
                            new["test"]
                        )
                    )


                    output.write(
                        f"[CHANGED] "
                        f"Similarity: "
                        f"{result['similarity'] * 100:.1f}%\n"
                    )


                    old_prefix = (
                        f"{name_a}:"
                        f"{old['line']} < "
                    )

                    new_prefix = (
                        f"{name_b}:"
                        f"{new['line']} > "
                    )


                    output.write(
                        old_prefix
                        +
                        old_text
                        +
                        "\n"
                    )


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
                        +
                        new_text
                        +
                        "\n"
                    )


                    if (
                        MARK_CHANGED_DIFFERENCES
                        and
                        new_marker
                    ):

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

                elif (
                    result_type
                    == "REMOVED"
                ):

                    old = (
                        result["old"]
                    )


                    text = (
                        build_display_text(
                            old["compare"],
                            old["test"]
                        )
                    )


                    output.write(
                        "[REMOVED]\n"
                    )

                    output.write(
                        f"{name_a}:"
                        f"{old['line']} < "
                        f"{text}\n\n"
                    )


                # ==========================================
                # ADDED
                # ==========================================

                elif (
                    result_type
                    == "ADDED"
                ):

                    new = (
                        result["new"]
                    )


                    text = (
                        build_display_text(
                            new["compare"],
                            new["test"]
                        )
                    )


                    output.write(
                        "[ADDED]\n"
                    )

                    output.write(
                        f"{name_b}:"
                        f"{new['line']} > "
                        f"{text}\n\n"
                    )


# ==========================================================
# HTML HEADER
# ==========================================================

def html_header(
    name_a,
    name_b
):

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Log Comparison</title>

<style>

body {{
    font-family:
        Consolas,
        "Courier New",
        monospace;

    background: #111827;
    color: #e5e7eb;

    margin: 0;
    padding: 25px;
}}

h1 {{
    color: #ffffff;
}}

.summary {{
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 8px;

    padding: 15px;
    margin-bottom: 25px;
}}

.file-a {{
    color: #38bdf8;
    font-weight: bold;
}}

.file-b {{
    color: #c084fc;
    font-weight: bold;
}}

.node {{
    margin-top: 28px;

    background: #1f2937;

    border-left:
        6px solid #f59e0b;

    padding: 12px;

    font-size: 18px;
    font-weight: bold;
}}

.node-missing {{
    border-left:
        6px solid #ef4444;
}}

.row {{
    white-space: pre-wrap;
    word-break: break-word;

    padding: 5px 8px;

    border-bottom:
        1px solid #1f2937;
}}

.changed {{
    background: #292524;
}}

.added {{
    background: #052e16;
}}

.removed {{
    background: #450a0a;
}}

.keyword {{
    background: #172554;
}}

.difference {{
    background: #dc2626;
    color: #ffffff;

    font-weight: bold;

    padding: 1px 2px;

    border-radius: 2px;
}}

.label {{
    color: #9ca3af;
    font-weight: bold;
}}

.similarity {{
    color: #fbbf24;
}}

.line-number {{
    color: #94a3b8;
}}

</style>

</head>

<body>

<h1>Log Comparison</h1>

<div class="summary">

File A:
<span class="file-a">
{html.escape(name_a)}
</span>

<br>

File B:
<span class="file-b">
{html.escape(name_b)}
</span>

</div>
"""


# ==========================================================
# HTML REPORT
# ==========================================================

def write_html_report(
    comparisons,
    file_a,
    file_b,
    keyword_rules
):

    name_a = (
        Path(file_a).name
    )

    name_b = (
        Path(file_b).name
    )


    with open(
        HTML_REPORT,
        "w",
        encoding="utf-8"
    ) as output:


        output.write(
            html_header(
                name_a,
                name_b
            )
        )


        for comparison in comparisons:

            node = (
                comparison["node"]
            )

            kind = (
                comparison["kind"]
            )


            if kind == "MATCH":

                title = (
                    f"NODE: {node}"
                )

                node_class = (
                    "node"
                )


            elif kind == "A_ONLY":

                title = (
                    f"NODE ONLY IN "
                    f"{name_a}: "
                    f"{node}"
                )

                node_class = (
                    "node node-missing"
                )


            elif kind == "B_ONLY":

                title = (
                    f"NODE ONLY IN "
                    f"{name_b}: "
                    f"{node}"
                )

                node_class = (
                    "node node-missing"
                )


            else:

                title = node

                node_class = (
                    "node"
                )


            output.write(
                f'<div class="{node_class}">'
                f'{html.escape(title)}'
                f'</div>\n'
            )


            for result in (
                comparison["results"]
            ):


                if not should_display(
                    result,
                    keyword_rules
                ):

                    continue


                result_type = (
                    result["type"]
                )


                # ==========================================
                # SAME / KEYWORD
                # ==========================================

                if result_type == "SAME":

                    old = (
                        result["old"]
                    )

                    new = (
                        result["new"]
                    )


                    text = (
                        build_display_text(
                            old["compare"],
                            old["test"]
                        )
                    )


                    output.write(
                        '<div class="row keyword">'
                    )

                    output.write(
                        '<span class="label">'
                        '[KEYWORD] '
                        '</span>'
                    )

                    output.write(
                        '<span class="file-a">'
                        +
                        html.escape(
                            name_a
                        )
                        +
                        '</span>'
                    )

                    output.write(
                        '<span class="line-number">'
                        f':{old["line"]}'
                        '</span>'
                    )

                    output.write(
                        ' | '
                    )

                    output.write(
                        '<span class="file-b">'
                        +
                        html.escape(
                            name_b
                        )
                        +
                        '</span>'
                    )

                    output.write(
                        '<span class="line-number">'
                        f':{new["line"]}'
                        '</span> '
                    )

                    output.write(
                        html.escape(
                            text
                        )
                    )

                    output.write(
                        '</div>\n'
                    )


                # ==========================================
                # CHANGED
                # ==========================================

                elif (
                    result_type
                    == "CHANGED"
                ):

                    old = (
                        result["old"]
                    )

                    new = (
                        result["new"]
                    )


                    old_text = (
                        build_display_text(
                            old["compare"],
                            old["test"]
                        )
                    )

                    new_text = (
                        build_display_text(
                            new["compare"],
                            new["test"]
                        )
                    )


                    (
                        old_html,
                        new_html
                    ) = (
                        html_diff(
                            old_text,
                            new_text
                        )
                    )


                    output.write(
                        '<div class="row changed">'
                    )

                    output.write(
                        '<span class="label">'
                        '[CHANGED] '
                        '</span>'
                    )

                    output.write(
                        '<span class="similarity">'
                        f'{result["similarity"] * 100:.1f}%'
                        '</span>'
                    )

                    output.write(
                        '</div>\n'
                    )


                    output.write(
                        '<div class="row changed">'
                    )

                    output.write(
                        '<span class="file-a">'
                        +
                        html.escape(
                            name_a
                        )
                        +
                        '</span>'
                    )

                    output.write(
                        '<span class="line-number">'
                        f':{old["line"]}'
                        '</span> '
                    )

                    output.write(
                        '&lt; '
                    )

                    output.write(
                        old_html
                    )

                    output.write(
                        '</div>\n'
                    )


                    output.write(
                        '<div class="row changed">'
                    )

                    output.write(
                        '<span class="file-b">'
                        +
                        html.escape(
                            name_b
                        )
                        +
                        '</span>'
                    )

                    output.write(
                        '<span class="line-number">'
                        f':{new["line"]}'
                        '</span> '
                    )

                    output.write(
                        '&gt; '
                    )

                    output.write(
                        new_html
                    )

                    output.write(
                        '</div>\n'
                    )


                # ==========================================
                # REMOVED
                # ==========================================

                elif (
                    result_type
                    == "REMOVED"
                ):

                    old = (
                        result["old"]
                    )


                    text = (
                        build_display_text(
                            old["compare"],
                            old["test"]
                        )
                    )


                    output.write(
                        '<div class="row removed">'
                    )

                    output.write(
                        '<span class="label">'
                        '[REMOVED] '
                        '</span>'
                    )

                    output.write(
                        '<span class="file-a">'
                        +
                        html.escape(
                            name_a
                        )
                        +
                        '</span>'
                    )

                    output.write(
                        '<span class="line-number">'
                        f':{old["line"]}'
                        '</span> '
                    )

                    output.write(
                        html.escape(
                            text
                        )
                    )

                    output.write(
                        '</div>\n'
                    )


                # ==========================================
                # ADDED
                # ==========================================

                elif (
                    result_type
                    == "ADDED"
                ):

                    new = (
                        result["new"]
                    )


                    text = (
                        build_display_text(
                            new["compare"],
                            new["test"]
                        )
                    )


                    output.write(
                        '<div class="row added">'
                    )

                    output.write(
                        '<span class="label">'
                        '[ADDED] '
                        '</span>'
                    )

                    output.write(
                        '<span class="file-b">'
                        +
                        html.escape(
                            name_b
                        )
                        +
                        '</span>'
                    )

                    output.write(
                        '<span class="line-number">'
                        f':{new["line"]}'
                        '</span> '
                    )

                    output.write(
                        html.escape(
                            text
                        )
                    )

                    output.write(
                        '</div>\n'
                    )


        output.write(
            """
</body>
</html>
"""
        )


# ==========================================================
# STATISTICS
# ==========================================================

def calculate_statistics(
    comparisons,
    keyword_rules
):

    stats = {

        "nodes":
            0,

        "matched_nodes":
            0,

        "a_only_nodes":
            0,

        "b_only_nodes":
            0,

        "changed":
            0,

        "added":
            0,

        "removed":
            0,

        "same":
            0,

        "keywords":
            0
    }


    for comparison in comparisons:

        if (
            comparison["kind"]
            != "PREAMBLE"
        ):

            stats["nodes"] += 1


        if (
            comparison["kind"]
            == "MATCH"
        ):

            stats[
                "matched_nodes"
            ] += 1


        elif (
            comparison["kind"]
            == "A_ONLY"
        ):

            stats[
                "a_only_nodes"
            ] += 1


        elif (
            comparison["kind"]
            == "B_ONLY"
        ):

            stats[
                "b_only_nodes"
            ] += 1


        for result in (
            comparison["results"]
        ):

            result_type = (
                result["type"]
            )


            if result_type == "SAME":

                stats["same"] += 1

                if result_matches_rules(
                    result,
                    keyword_rules
                ):

                    stats[
                        "keywords"
                    ] += 1


            elif result_type == "CHANGED":

                stats[
                    "changed"
                ] += 1


            elif result_type == "ADDED":

                stats[
                    "added"
                ] += 1


            elif result_type == "REMOVED":

                stats[
                    "removed"
                ] += 1


    return stats


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


    file_a = (
        sys.argv[1]
    )

    file_b = (
        sys.argv[2]
    )


    if not Path(
        file_a
    ).is_file():

        print(
            f"File not found: "
            f"{file_a}"
        )

        sys.exit(1)


    if not Path(
        file_b
    ).is_file():

        print(
            f"File not found: "
            f"{file_b}"
        )

        sys.exit(1)


    total_start = (
        time.perf_counter()
    )


    # ======================================================
    # RULES
    # ======================================================

    create_rule_files()


    keyword_rules = (
        load_rules(
            KEYWORD_FILE
        )
    )


    exclude_rules = (
        load_rules(
            EXCLUDE_FILE
        )
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
    # READ FILE A
    # ======================================================

    print()

    print(
        f"Reading A: "
        f"{file_a}"
    )


    lines_a = (
        read_file(
            file_a
        )
    )


    print(
        f"Lines A: "
        f"{len(lines_a):,}"
    )


    # ======================================================
    # READ FILE B
    # ======================================================

    print()

    print(
        f"Reading B: "
        f"{file_b}"
    )


    lines_b = (
        read_file(
            file_b
        )
    )


    print(
        f"Lines B: "
        f"{len(lines_b):,}"
    )


    # ======================================================
    # SPLIT INTO NODE BLOCKS
    # ======================================================

    print()

    print(
        "Finding Node name blocks..."
    )


    (
        preamble_a,
        blocks_a
    ) = split_into_node_blocks(
        lines_a
    )


    (
        preamble_b,
        blocks_b
    ) = split_into_node_blocks(
        lines_b
    )


    print(
        f"Nodes A: "
        f"{len(blocks_a):,}"
    )

    print(
        f"Nodes B: "
        f"{len(blocks_b):,}"
    )


    # ======================================================
    # BUILD NODE-ALIGNED COMPARISON
    # ======================================================

    print()

    print(
        "Aligning Node name blocks..."
    )


    comparisons = (
        build_comparisons(
            preamble_a,
            blocks_a,
            preamble_b,
            blocks_b,
            exclude_rules
        )
    )


    # ======================================================
    # STATISTICS
    # ======================================================

    stats = (
        calculate_statistics(
            comparisons,
            keyword_rules
        )
    )


    # ======================================================
    # TXT
    # ======================================================

    print()

    print(
        "Writing TXT report..."
    )


    write_text_report(
        comparisons,
        file_a,
        file_b,
        keyword_rules
    )


    # ======================================================
    # HTML
    # ======================================================

    print(
        "Writing HTML report..."
    )


    write_html_report(
        comparisons,
        file_a,
        file_b,
        keyword_rules
    )


    # ======================================================
    # DONE
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
        f"Matched Nodes: "
        f"{stats['matched_nodes']:,}"
    )

    print(
        f"Only in A:     "
        f"{stats['a_only_nodes']:,}"
    )

    print(
        f"Only in B:     "
        f"{stats['b_only_nodes']:,}"
    )

    print(
        "-" * 70
    )

    print(
        f"SAME:          "
        f"{stats['same']:,}"
    )

    print(
        f"KEYWORDS:      "
        f"{stats['keywords']:,}"
    )

    print(
        f"CHANGED:       "
        f"{stats['changed']:,}"
    )

    print(
        f"ADDED:         "
        f"{stats['added']:,}"
    )

    print(
        f"REMOVED:       "
        f"{stats['removed']:,}"
    )

    print(
        "-" * 70
    )

    print(
        f"Total time:    "
        f"{format_time(total_elapsed)}"
    )

    print()

    print(
        f"TXT report:    "
        f"{TEXT_REPORT}"
    )

    print(
        f"HTML report:   "
        f"{HTML_REPORT}"
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
        "=" * 70
    )


if __name__ == "__main__":

    main()