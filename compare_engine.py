import sys
import time
import difflib
import re
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

# Ignore first N whitespace-separated columns.
IGNORE_FIRST_COLUMNS = 5

# Remove timestamps during comparison.
REMOVE_TIMESTAMPS = True

# Show all SAME lines?
SHOW_SAME = False


# ==========================================================
# ALWAYS SHOW KEYWORDS
# ==========================================================

ALWAYS_SHOW_KEYWORDS = [
    "Start",
    "Node name",
    "Test '",
]

ALWAYS_SHOW_IGNORE_CASE = True


# ==========================================================
# REPEAT COMPRESSION
# ==========================================================

COMPRESS_REPEATS = True

MIN_REPEAT_COUNT = 3


# ==========================================================
# COMPARISON SETTINGS
# ==========================================================

CHANGE_THRESHOLD = 0.55

CHANGE_WINDOW = 30

MIN_LENGTH_RATIO = 0.60


# ==========================================================
# DIFFERENCE MARKING
# ==========================================================

# Mark exact differences in CHANGED lines using ^ characters.
MARK_CHANGED_DIFFERENCES = True

# Character used to mark differences.
DIFFERENCE_MARKER = "^"


# ==========================================================
# PROGRESS SETTINGS
# ==========================================================

PROGRESS_BAR_WIDTH = 30

PROGRESS_UPDATE_SECONDS = 0.15


# ==========================================================
# TIMESTAMP REGEX
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
# FORMAT TIME
# ==========================================================

def format_time(seconds):

    if seconds < 0:
        seconds = 0

    seconds = int(seconds)

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = (
        seconds % 60
    )

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
# PROGRESS BAR
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
                now
                - self.last_update
                < PROGRESS_UPDATE_SECONDS
            ):

                return

        self.last_update = now

        elapsed = (
            now
            - self.start_time
        )

        percentage = (
            current
            / self.total
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

        if elapsed > 0:

            speed = (
                current
                / elapsed
            )

        else:

            speed = 0


        if speed > 0:

            remaining = (
                self.total
                - current
            )

            eta = (
                remaining
                / speed
            )

            eta_text = (
                format_time(
                    eta
                )
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
# NORMALIZE LINE
# ==========================================================

def normalize_line(line):

    text = line


    # ======================================================
    # REMOVE FIRST N COLUMNS
    # ======================================================

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


    # ======================================================
    # REMOVE TIMESTAMPS
    # ======================================================

    if REMOVE_TIMESTAMPS:

        text = (
            TIMESTAMP_PATTERN.sub(
                "",
                text
            )
        )


    # ======================================================
    # CLEAN WHITESPACE
    # ======================================================

    text = " ".join(
        text.split()
    )


    return text


# ==========================================================
# ALWAYS SHOW?
# ==========================================================

def should_always_show(text):

    if not text:
        return False


    if ALWAYS_SHOW_IGNORE_CASE:

        check_text = (
            text.lower()
        )

        for keyword in (
            ALWAYS_SHOW_KEYWORDS
        ):

            if (
                keyword.lower()
                in check_text
            ):

                return True

    else:

        for keyword in (
            ALWAYS_SHOW_KEYWORDS
        ):

            if keyword in text:

                return True


    return False


# ==========================================================
# READ FILE
# ==========================================================

def read_file(path):

    original_lines = []

    normalized_lines = []


    with open(
        path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        for line in file:

            original = (
                line.rstrip(
                    "\r\n"
                )
            )

            original_lines.append(
                original
            )

            normalized_lines.append(
                normalize_line(
                    original
                )
            )


    return (
        original_lines,
        normalized_lines
    )


# ==========================================================
# LENGTH FILTER
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


    ratio = (
        shorter
        / longer
    )


    return (
        ratio
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


    return matcher.ratio()


# ==========================================================
# DIFFERENCE MARKER
# ==========================================================

def create_difference_markers(
    old_text,
    new_text
):

    """
    Creates marker lines using ^ characters.

    Example:

    OLD:
    CPLD status = 0x20

    NEW:
    CPLD status = 0x30

                   ^
    """

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


        # Equal text does not need marking.
        if tag == "equal":

            continue


        # --------------------------------------------------
        # REPLACE
        # --------------------------------------------------

        if tag == "replace":

            for index in range(
                old_start,
                old_end
            ):

                old_marker[index] = (
                    DIFFERENCE_MARKER
                )


            for index in range(
                new_start,
                new_end
            ):

                new_marker[index] = (
                    DIFFERENCE_MARKER
                )


        # --------------------------------------------------
        # DELETE
        # --------------------------------------------------

        elif tag == "delete":

            for index in range(
                old_start,
                old_end
            ):

                old_marker[index] = (
                    DIFFERENCE_MARKER
                )


        # --------------------------------------------------
        # INSERT
        # --------------------------------------------------

        elif tag == "insert":

            for index in range(
                new_start,
                new_end
            ):

                new_marker[index] = (
                    DIFFERENCE_MARKER
                )


    old_marker = "".join(
        old_marker
    ).rstrip()

    new_marker = "".join(
        new_marker
    ).rstrip()


    return (
        old_marker,
        new_marker
    )


# ==========================================================
# CREATE RESULT
# ==========================================================

def make_result(
    result_type,
    old_line=None,
    new_line=None,
    old_text=None,
    new_text=None,
    old_compare=None,
    new_compare=None,
    similarity_value=None
):

    return {

        "type":
            result_type,

        "old_line":
            old_line,

        "new_line":
            new_line,

        "old_text":
            old_text,

        "new_text":
            new_text,

        "old_compare":
            old_compare,

        "new_compare":
            new_compare,

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

    removed_count = len(
        removed
    )

    added_count = len(
        added
    )


    # ======================================================
    # ONLY ADDED
    # ======================================================

    if removed_count == 0:

        for item in added:

            results.append(
                make_result(
                    "ADDED",

                    new_line=
                        item["line"],

                    new_text=
                        item["text"],

                    new_compare=
                        item["compare"]
                )
            )

        return results


    # ======================================================
    # ONLY REMOVED
    # ======================================================

    if added_count == 0:

        for item in removed:

            results.append(
                make_result(
                    "REMOVED",

                    old_line=
                        item["line"],

                    old_text=
                        item["text"],

                    old_compare=
                        item["compare"]
                )
            )

        return results


    # ======================================================
    # FIND CHANGED PAIRS
    # ======================================================

    for (
        removed_index,
        old_item
    ) in enumerate(
        removed
    ):

        old_compare = (
            old_item[
                "compare"
            ]
        )

        best_index = None

        best_score = 0.0


        # --------------------------------------------------
        # ESTIMATE POSITION
        # --------------------------------------------------

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


        # --------------------------------------------------
        # BUILD CANDIDATE LIST
        # --------------------------------------------------

        candidate_order = []


        for distance in range(
            0,
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
                    0
                    <= candidate
                    < added_count
                ):

                    if (
                        candidate
                        not in candidate_order
                    ):

                        candidate_order.append(
                            candidate
                        )


        # --------------------------------------------------
        # COMPARE CANDIDATES
        # --------------------------------------------------

        for index in candidate_order:

            if index in used_added:

                continue


            new_item = (
                added[
                    index
                ]
            )

            new_compare = (
                new_item[
                    "compare"
                ]
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


        # ==================================================
        # CHANGED
        # ==================================================

        if (
            best_index is not None
            and
            best_score
            >= CHANGE_THRESHOLD
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

                    old_line=
                        old_item[
                            "line"
                        ],

                    new_line=
                        new_item[
                            "line"
                        ],

                    old_text=
                        old_item[
                            "text"
                        ],

                    new_text=
                        new_item[
                            "text"
                        ],

                    old_compare=
                        old_item[
                            "compare"
                        ],

                    new_compare=
                        new_item[
                            "compare"
                        ],

                    similarity_value=
                        best_score
                )
            )


        # ==================================================
        # REMOVED
        # ==================================================

        else:

            results.append(
                make_result(
                    "REMOVED",

                    old_line=
                        old_item[
                            "line"
                        ],

                    old_text=
                        old_item[
                            "text"
                        ],

                    old_compare=
                        old_item[
                            "compare"
                        ]
                )
            )


    # ======================================================
    # REMAINING ADDED
    # ======================================================

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

                new_line=
                    new_item[
                        "line"
                    ],

                new_text=
                    new_item[
                        "text"
                    ],

                new_compare=
                    new_item[
                        "compare"
                    ]
            )
        )


    return results


# ==========================================================
# COMPARE FILES
# ==========================================================

def compare_files(
    original_a,
    normalized_a,
    original_b,
    normalized_b
):

    print()

    print(
        "Building line comparison map..."
    )


    matcher = (
        difflib.SequenceMatcher(
            None,
            normalized_a,
            normalized_b,
            autojunk=True
        )
    )


    opcodes = (
        matcher.get_opcodes()
    )


    print(
        f"Comparison blocks: "
        f"{len(opcodes):,}"
    )


    total_lines = max(
        len(normalized_a),
        len(normalized_b)
    )


    progress = Progress(
        total_lines,
        "Analyzing"
    )


    results = []

    processed = 0


    for (
        tag,
        a_start,
        a_end,
        b_start,
        b_end
    ) in opcodes:


        # ==================================================
        # SAME
        # ==================================================

        if tag == "equal":

            count = (
                a_end
                - a_start
            )


            for offset in range(
                count
            ):

                old_index = (
                    a_start
                    + offset
                )

                new_index = (
                    b_start
                    + offset
                )


                results.append(
                    make_result(
                        "SAME",

                        old_line=
                            old_index + 1,

                        new_line=
                            new_index + 1,

                        old_text=
                            original_a[
                                old_index
                            ],

                        new_text=
                            original_b[
                                new_index
                            ],

                        old_compare=
                            normalized_a[
                                old_index
                            ],

                        new_compare=
                            normalized_b[
                                new_index
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

                        old_line=
                            index + 1,

                        old_text=
                            original_a[
                                index
                            ],

                        old_compare=
                            normalized_a[
                                index
                            ]
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

                        new_line=
                            index + 1,

                        new_text=
                            original_b[
                                index
                            ],

                        new_compare=
                            normalized_b[
                                index
                            ]
                    )
                )


        # ==================================================
        # REPLACE
        # ==================================================

        elif tag == "replace":

            removed = []

            added = []


            for index in range(
                a_start,
                a_end
            ):

                removed.append({

                    "line":
                        index + 1,

                    "text":
                        original_a[
                            index
                        ],

                    "compare":
                        normalized_a[
                            index
                        ]
                })


            for index in range(
                b_start,
                b_end
            ):

                added.append({

                    "line":
                        index + 1,

                    "text":
                        original_b[
                            index
                        ],

                    "compare":
                        normalized_b[
                            index
                        ]
                })


            block_results = (
                pair_changed_lines(
                    removed,
                    added
                )
            )


            results.extend(
                block_results
            )


        processed = max(
            processed,
            a_end,
            b_end
        )


        progress.update(
            processed
        )


    progress.finish()

    return results


# ==========================================================
# CAN COMPRESS?
# ==========================================================

def can_compress(
    previous,
    current
):

    if previous["type"] not in (
        "ADDED",
        "REMOVED"
    ):

        return False


    if (
        current["type"]
        != previous["type"]
    ):

        return False


    # ======================================================
    # REMOVED
    # ======================================================

    if (
        current["type"]
        == "REMOVED"
    ):

        if (
            current[
                "old_compare"
            ]
            !=
            previous[
                "old_compare"
            ]
        ):

            return False


        if (
            current[
                "old_line"
            ]
            !=
            previous[
                "old_line"
            ] + 1
        ):

            return False


    # ======================================================
    # ADDED
    # ======================================================

    elif (
        current["type"]
        == "ADDED"
    ):

        if (
            current[
                "new_compare"
            ]
            !=
            previous[
                "new_compare"
            ]
        ):

            return False


        if (
            current[
                "new_line"
            ]
            !=
            previous[
                "new_line"
            ] + 1
        ):

            return False


    return True


# ==========================================================
# COMPRESS RESULTS
# ==========================================================

def compress_results(
    results
):

    if not COMPRESS_REPEATS:

        return results


    compressed = []

    index = 0


    while index < len(
        results
    ):

        current = (
            results[
                index
            ]
        )


        if current["type"] not in (
            "ADDED",
            "REMOVED"
        ):

            compressed.append(
                current
            )

            index += 1

            continue


        group = [
            current
        ]


        next_index = (
            index + 1
        )


        while (
            next_index
            < len(results)
        ):

            previous = (
                group[-1]
            )

            candidate = (
                results[
                    next_index
                ]
            )


            if not can_compress(
                previous,
                candidate
            ):

                break


            group.append(
                candidate
            )

            next_index += 1


        # ==================================================
        # CREATE GROUP
        # ==================================================

        if (
            len(group)
            >= MIN_REPEAT_COUNT
        ):

            first = group[0]

            last = group[-1]


            if (
                current["type"]
                == "REMOVED"
            ):

                compressed.append({

                    "type":
                        "REMOVED_GROUP",

                    "count":
                        len(group),

                    "start_line":
                        first[
                            "old_line"
                        ],

                    "end_line":
                        last[
                            "old_line"
                        ],

                    "compare":
                        first[
                            "old_compare"
                        ]
                })


            else:

                compressed.append({

                    "type":
                        "ADDED_GROUP",

                    "count":
                        len(group),

                    "start_line":
                        first[
                            "new_line"
                        ],

                    "end_line":
                        last[
                            "new_line"
                        ],

                    "compare":
                        first[
                            "new_compare"
                        ]
                })


        else:

            compressed.extend(
                group
            )


        index = next_index


    return compressed


# ==========================================================
# WRITE REPORT
# ==========================================================

def write_report(
    results,
    file_a,
    file_b,
    output_file
):

    name_a = (
        Path(file_a).name
    )

    name_b = (
        Path(file_b).name
    )


    changed_count = 0

    added_count = 0

    removed_count = 0

    keyword_count = 0

    added_groups = 0

    removed_groups = 0


    actual_same = sum(
        1
        for item in results
        if item["type"] == "SAME"
    )


    print()

    print(
        "Compressing repeated events..."
    )


    report_results = (
        compress_results(
            results
        )
    )


    print(
        f"Raw results:    "
        f"{len(results):,}"
    )

    print(
        f"Report records: "
        f"{len(report_results):,}"
    )


    print()

    print(
        "Writing report..."
    )


    progress = Progress(
        len(report_results),
        "Writing"
    )


    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as output:


        for (
            index,
            item
        ) in enumerate(
            report_results,
            start=1
        ):

            item_type = (
                item["type"]
            )


            # ==============================================
            # SAME
            # ==============================================

            if item_type == "SAME":

                always_show = (
                    should_always_show(
                        item[
                            "old_compare"
                        ]
                    )
                )


                if (
                    SHOW_SAME
                    or always_show
                ):

                    if always_show:

                        keyword_count += 1

                        output.write(
                            "[KEYWORD]\n"
                        )

                    else:

                        output.write(
                            "[SAME]\n"
                        )


                    output.write(
                        f"{name_a}:"
                        f"{item['old_line']} "
                        f"| "
                        f"{name_b}:"
                        f"{item['new_line']} "
                        f"  "
                        f"{item['old_compare']}\n\n"
                    )


            # ==============================================
            # CHANGED
            # ==============================================

            elif (
                item_type
                == "CHANGED"
            ):

                changed_count += 1


                percent = (
                    item[
                        "similarity"
                    ]
                    * 100
                )


                old_text = (
                    item[
                        "old_compare"
                    ]
                )

                new_text = (
                    item[
                        "new_compare"
                    ]
                )


                output.write(
                    f"[CHANGED] "
                    f"Similarity: "
                    f"{percent:.1f}%\n"
                )


                old_prefix = (
                    f"{name_a}:"
                    f"{item['old_line']} "
                    f"< "
                )

                new_prefix = (
                    f"{name_b}:"
                    f"{item['new_line']} "
                    f"> "
                )


                output.write(
                    f"{old_prefix}"
                    f"{old_text}\n"
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
                    f"{new_prefix}"
                    f"{new_text}\n"
                )


                if MARK_CHANGED_DIFFERENCES:

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


            # ==============================================
            # REMOVED
            # ==============================================

            elif (
                item_type
                == "REMOVED"
            ):

                removed_count += 1


                output.write(
                    "[REMOVED]\n"
                )


                output.write(
                    f"{name_a}:"
                    f"{item['old_line']} "
                    f"< "
                    f"{item['old_compare']}\n\n"
                )


            # ==============================================
            # ADDED
            # ==============================================

            elif (
                item_type
                == "ADDED"
            ):

                added_count += 1


                output.write(
                    "[ADDED]\n"
                )


                output.write(
                    f"{name_b}:"
                    f"{item['new_line']} "
                    f"> "
                    f"{item['new_compare']}\n\n"
                )


            # ==============================================
            # REMOVED GROUP
            # ==============================================

            elif (
                item_type
                == "REMOVED_GROUP"
            ):

                removed_count += (
                    item[
                        "count"
                    ]
                )

                removed_groups += 1


                output.write(
                    f"[REMOVED ×"
                    f"{item['count']}]\n"
                )


                output.write(
                    f"{name_a}:"
                    f"{item['start_line']}"
                    f"-"
                    f"{item['end_line']} "
                    f"< "
                    f"{item['compare']}\n\n"
                )


            # ==============================================
            # ADDED GROUP
            # ==============================================

            elif (
                item_type
                == "ADDED_GROUP"
            ):

                added_count += (
                    item[
                        "count"
                    ]
                )

                added_groups += 1


                output.write(
                    f"[ADDED ×"
                    f"{item['count']}]\n"
                )


                output.write(
                    f"{name_b}:"
                    f"{item['start_line']}"
                    f"-"
                    f"{item['end_line']} "
                    f"> "
                    f"{item['compare']}\n\n"
                )


            progress.update(
                index
            )


        # ==================================================
        # SUMMARY
        # ==================================================

        output.write(
            "=" * 80
            + "\n"
        )

        output.write(
            "SUMMARY\n"
        )

        output.write(
            "=" * 80
            + "\n"
        )


        output.write(
            f"SAME:             "
            f"{actual_same:,}"
        )


        if not SHOW_SAME:

            output.write(
                " "
                "(hidden except keywords)"
            )


        output.write(
            "\n"
        )


        output.write(
            f"KEYWORDS shown:   "
            f"{keyword_count:,}\n"
        )


        output.write(
            f"CHANGED:          "
            f"{changed_count:,}\n"
        )


        output.write(
            f"ADDED lines:      "
            f"{added_count:,}\n"
        )


        output.write(
            f"REMOVED lines:    "
            f"{removed_count:,}\n"
        )


        output.write(
            f"ADDED groups:     "
            f"{added_groups:,}\n"
        )


        output.write(
            f"REMOVED groups:   "
            f"{removed_groups:,}\n"
        )


    progress.finish()


    return {

        "same":
            actual_same,

        "keywords":
            keyword_count,

        "changed":
            changed_count,

        "added":
            added_count,

        "removed":
            removed_count,

        "report_records":
            len(
                report_results
            )
    }


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


    # ======================================================
    # CHECK FILES
    # ======================================================

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
    # READ FILE A
    # ======================================================

    print()

    print(
        f"Reading A: "
        f"{file_a}"
    )


    (
        original_a,
        normalized_a
    ) = read_file(
        file_a
    )


    print(
        f"Lines A: "
        f"{len(original_a):,}"
    )


    # ======================================================
    # READ FILE B
    # ======================================================

    print()

    print(
        f"Reading B: "
        f"{file_b}"
    )


    (
        original_b,
        normalized_b
    ) = read_file(
        file_b
    )


    print(
        f"Lines B: "
        f"{len(original_b):,}"
    )


    # ======================================================
    # SETTINGS
    # ======================================================

    print()

    print(
        "=" * 70
    )

    print(
        "COMPARE SETTINGS"
    )

    print(
        "=" * 70
    )


    print(
        f"Ignore first columns : "
        f"{IGNORE_FIRST_COLUMNS}"
    )


    print(
        f"Remove timestamps    : "
        f"{REMOVE_TIMESTAMPS}"
    )


    print(
        f"Show SAME            : "
        f"{SHOW_SAME}"
    )


    print(
        f"Always show keywords : "
        f"{len(ALWAYS_SHOW_KEYWORDS)}"
    )


    for keyword in (
        ALWAYS_SHOW_KEYWORDS
    ):

        print(
            f"  - {keyword}"
        )


    print(
        f"Compress repeats     : "
        f"{COMPRESS_REPEATS}"
    )


    print(
        f"Minimum repeats      : "
        f"{MIN_REPEAT_COUNT}"
    )


    print(
        f"Change threshold     : "
        f"{CHANGE_THRESHOLD * 100:.0f}%"
    )


    print(
        f"Change window        : "
        f"{CHANGE_WINDOW}"
    )


    print(
        f"Mark differences     : "
        f"{MARK_CHANGED_DIFFERENCES}"
    )


    print(
        "=" * 70
    )


    # ======================================================
    # COMPARE
    # ======================================================

    compare_start = (
        time.perf_counter()
    )


    results = compare_files(
        original_a,
        normalized_a,
        original_b,
        normalized_b
    )


    compare_elapsed = (
        time.perf_counter()
        - compare_start
    )


    # ======================================================
    # WRITE REPORT
    # ======================================================

    output_file = (
        "compare_results.txt"
    )


    summary = write_report(
        results,
        file_a,
        file_b,
        output_file
    )


    total_elapsed = (
        time.perf_counter()
        - total_start
    )


    # ======================================================
    # FINAL
    # ======================================================

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
        f"SAME:       "
        f"{summary['same']:,}"
        +
        (
            " "
            "(hidden except keywords)"
            if not SHOW_SAME
            else ""
        )
    )


    print(
        f"KEYWORDS:   "
        f"{summary['keywords']:,}"
    )


    print(
        f"CHANGED:    "
        f"{summary['changed']:,}"
    )


    print(
        f"ADDED:      "
        f"{summary['added']:,}"
    )


    print(
        f"REMOVED:    "
        f"{summary['removed']:,}"
    )


    print(
        f"Report rows: "
        f"{summary['report_records']:,}"
    )


    print(
        "-" * 70
    )


    print(
        f"Compare time: "
        f"{format_time(compare_elapsed)}"
    )


    print(
        f"Total time:   "
        f"{format_time(total_elapsed)}"
    )


    print(
        f"Results:      "
        f"{output_file}"
    )


    print(
        "=" * 70
    )


# ==========================================================
# START
# ==========================================================

if __name__ == "__main__":

    main()