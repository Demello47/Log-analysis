import sys
import time
import difflib
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

# Насколько строки должны быть похожи,
# чтобы считать их CHANGED.
#
# 0.55 = 55%
CHANGE_THRESHOLD = 0.55


# Максимальное количество строк вокруг предполагаемой
# позиции, которые проверяем при поиске CHANGED.
#
# Чем меньше число -> быстрее.
# Чем больше -> выше шанс правильно сопоставить
# сильно смещенные строки.
CHANGE_WINDOW = 30


# Если длина двух строк сильно отличается,
# не запускаем дорогой SequenceMatcher.
#
# 0.60 означает:
# короткая строка должна быть минимум 60%
# длины длинной строки.
MIN_LENGTH_RATIO = 0.60


# Размер progress bar
PROGRESS_BAR_WIDTH = 30


# Как часто обновлять progress bar в секундах
PROGRESS_UPDATE_SECONDS = 0.15


# ==========================================================
# FORMAT TIME
# ==========================================================

def format_time(seconds):

    if seconds < 0:
        seconds = 0

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


# ==========================================================
# PROGRESS
# ==========================================================

class Progress:

    def __init__(self, total, name="Comparing"):

        self.total = max(total, 1)
        self.name = name

        self.start_time = time.perf_counter()
        self.last_update = 0

        self.current = 0


    def update(self, current, force=False):

        self.current = min(
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
            self.current
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


        # --------------------------------------------------
        # Speed
        # --------------------------------------------------

        if elapsed > 0:

            speed = (
                self.current
                / elapsed
            )

        else:

            speed = 0


        # --------------------------------------------------
        # ETA
        # --------------------------------------------------

        if (
            speed > 0
            and self.current > 0
        ):

            remaining = (
                self.total
                - self.current
            )

            eta = (
                remaining
                / speed
            )

            eta_text = format_time(
                eta
            )

        else:

            eta_text = "--:--"


        elapsed_text = format_time(
            elapsed
        )


        print(
            f"\r"
            f"{self.name}: "
            f"[{bar}] "
            f"{percentage * 100:6.2f}% "
            f"| {self.current}/{self.total} "
            f"| {speed:,.0f} lines/s "
            f"| Elapsed {elapsed_text} "
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
# READ FILE
# ==========================================================

def read_file(path):

    lines = []

    with open(
        path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:

        for line in file:

            lines.append(
                line.rstrip("\r\n")
            )

    return lines


# ==========================================================
# FAST LENGTH CHECK
# ==========================================================

def length_is_reasonable(
    line_a,
    line_b
):

    len_a = len(line_a)
    len_b = len(line_b)


    # Both empty
    if (
        len_a == 0
        and len_b == 0
    ):
        return True


    # One empty
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


    ratio = (
        shorter
        / longer
    )


    return (
        ratio >= MIN_LENGTH_RATIO
    )


# ==========================================================
# LINE SIMILARITY
# ==========================================================

def similarity(
    line_a,
    line_b
):

    # Exact match
    if line_a == line_b:
        return 1.0


    # Cheap length filter first
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


    # ------------------------------------------------------
    # quick_ratio() is cheaper than ratio().
    #
    # If even quick estimate is below threshold,
    # don't calculate full ratio.
    # ------------------------------------------------------

    quick = matcher.quick_ratio()


    if quick < CHANGE_THRESHOLD:
        return 0.0


    return matcher.ratio()


# ==========================================================
# PAIR REPLACED LINES
#
# Try to determine whether:
#
# removed line + added line
#
# are actually one CHANGED line.
# ==========================================================

def pair_changed_lines(
    removed,
    added
):

    results = []

    used_added = set()


    # ------------------------------------------------------
    # Nothing on one side
    # ------------------------------------------------------

    if not removed:

        for (
            new_line_num,
            new_text
        ) in added:

            results.append({

                "type":
                    "ADDED",

                "old_line":
                    None,

                "new_line":
                    new_line_num,

                "old_text":
                    None,

                "new_text":
                    new_text,

                "similarity":
                    None
            })

        return results


    if not added:

        for (
            old_line_num,
            old_text
        ) in removed:

            results.append({

                "type":
                    "REMOVED",

                "old_line":
                    old_line_num,

                "new_line":
                    None,

                "old_text":
                    old_text,

                "new_text":
                    None,

                "similarity":
                    None
            })

        return results


    # ------------------------------------------------------
    # Position mapping
    #
    # If block sizes differ, estimate where each removed
    # line should be located on the added side.
    # ------------------------------------------------------

    removed_count = len(
        removed
    )

    added_count = len(
        added
    )


    for removed_index, (
        old_line_num,
        old_text
    ) in enumerate(
        removed
    ):

        best_index = None
        best_score = 0.0


        # --------------------------------------------------
        # Estimate corresponding position
        # --------------------------------------------------

        if removed_count <= 1:

            estimated_index = 0

        else:

            position_ratio = (
                removed_index
                / (
                    removed_count - 1
                )
            )

            estimated_index = int(
                position_ratio
                * max(
                    added_count - 1,
                    0
                )
            )


        # --------------------------------------------------
        # Search only near estimated position
        # --------------------------------------------------

        start_index = max(
            0,
            estimated_index
            - CHANGE_WINDOW
        )

        end_index = min(
            added_count,
            estimated_index
            + CHANGE_WINDOW
            + 1
        )


        # --------------------------------------------------
        # First try exact same relative position.
        #
        # This is extremely common in logs.
        # --------------------------------------------------

        candidate_order = []


        if (
            estimated_index
            >= start_index
            and estimated_index
            < end_index
        ):

            candidate_order.append(
                estimated_index
            )


        # --------------------------------------------------
        # Then expand around position:
        #
        # 0
        # -1
        # +1
        # -2
        # +2
        # ...
        # --------------------------------------------------

        for distance in range(
            1,
            CHANGE_WINDOW + 1
        ):

            left = (
                estimated_index
                - distance
            )

            right = (
                estimated_index
                + distance
            )


            if (
                left >= start_index
                and left < end_index
            ):

                candidate_order.append(
                    left
                )


            if (
                right >= start_index
                and right < end_index
            ):

                candidate_order.append(
                    right
                )


        # --------------------------------------------------
        # Compare candidates
        # --------------------------------------------------

        for index in candidate_order:

            if index in used_added:
                continue


            (
                new_line_num,
                new_text
            ) = added[index]


            # Cheap length check
            if not length_is_reasonable(
                old_text,
                new_text
            ):
                continue


            score = similarity(
                old_text,
                new_text
            )


            if score > best_score:

                best_score = score
                best_index = index


            # Very strong match.
            # No need to continue searching.
            if best_score >= 0.98:
                break


        # --------------------------------------------------
        # CHANGED
        # --------------------------------------------------

        if (
            best_index is not None
            and best_score
            >= CHANGE_THRESHOLD
        ):

            (
                new_line_num,
                new_text
            ) = added[
                best_index
            ]


            used_added.add(
                best_index
            )


            results.append({

                "type":
                    "CHANGED",

                "old_line":
                    old_line_num,

                "new_line":
                    new_line_num,

                "old_text":
                    old_text,

                "new_text":
                    new_text,

                "similarity":
                    best_score
            })


        # --------------------------------------------------
        # REMOVED
        # --------------------------------------------------

        else:

            results.append({

                "type":
                    "REMOVED",

                "old_line":
                    old_line_num,

                "new_line":
                    None,

                "old_text":
                    old_text,

                "new_text":
                    None,

                "similarity":
                    None
            })


    # ------------------------------------------------------
    # Remaining added lines
    # ------------------------------------------------------

    for index, (
        new_line_num,
        new_text
    ) in enumerate(
        added
    ):

        if index in used_added:
            continue


        results.append({

            "type":
                "ADDED",

            "old_line":
                None,

            "new_line":
                new_line_num,

            "old_text":
                None,

            "new_text":
                new_text,

            "similarity":
                None
        })


    return results


# ==========================================================
# COMPARE FILES
# ==========================================================

def compare_files(
    lines_a,
    lines_b
):

    print()
    print(
        "Building line comparison map..."
    )


    # ======================================================
    # MAIN SEQUENCE MATCHER
    #
    # autojunk=True is important for large repetitive logs.
    # ======================================================

    matcher = difflib.SequenceMatcher(
        None,
        lines_a,
        lines_b,
        autojunk=True
    )


    opcodes = matcher.get_opcodes()


    print(
        f"Comparison blocks: "
        f"{len(opcodes)}"
    )


    # ======================================================
    # Progress is based on the larger input file.
    # ======================================================

    total_lines = max(
        len(lines_a),
        len(lines_b)
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


                results.append({

                    "type":
                        "SAME",

                    "old_line":
                        old_index + 1,

                    "new_line":
                        new_index + 1,

                    "old_text":
                        lines_a[
                            old_index
                        ],

                    "new_text":
                        lines_b[
                            new_index
                        ],

                    "similarity":
                        1.0
                })


            processed = max(
                processed,
                a_end,
                b_end
            )


        # ==================================================
        # REMOVED
        # ==================================================

        elif tag == "delete":

            for index in range(
                a_start,
                a_end
            ):

                results.append({

                    "type":
                        "REMOVED",

                    "old_line":
                        index + 1,

                    "new_line":
                        None,

                    "old_text":
                        lines_a[
                            index
                        ],

                    "new_text":
                        None,

                    "similarity":
                        None
                })


            processed = max(
                processed,
                a_end,
                b_end
            )


        # ==================================================
        # ADDED
        # ==================================================

        elif tag == "insert":

            for index in range(
                b_start,
                b_end
            ):

                results.append({

                    "type":
                        "ADDED",

                    "old_line":
                        None,

                    "new_line":
                        index + 1,

                    "old_text":
                        None,

                    "new_text":
                        lines_b[
                            index
                        ],

                    "similarity":
                        None
                })


            processed = max(
                processed,
                a_end,
                b_end
            )


        # ==================================================
        # REPLACE
        # ==================================================

        elif tag == "replace":

            removed = [

                (
                    index + 1,
                    lines_a[
                        index
                    ]
                )

                for index in range(
                    a_start,
                    a_end
                )
            ]


            added = [

                (
                    index + 1,
                    lines_b[
                        index
                    ]
                )

                for index in range(
                    b_start,
                    b_end
                )
            ]


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
# WRITE REPORT
# ==========================================================

def write_report(
    results,
    file_a,
    file_b,
    output_file
):

    print()
    print(
        "Writing report..."
    )


    same_count = 0
    changed_count = 0
    added_count = 0
    removed_count = 0


    progress = Progress(
        len(results),
        "Writing"
    )


    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as output:


        output.write(
            f"FILE A: {file_a}\n"
        )

        output.write(
            f"FILE B: {file_b}\n"
        )

        output.write(
            "=" * 80
            + "\n\n"
        )


        for index, item in enumerate(
            results,
            start=1
        ):

            item_type = item[
                "type"
            ]


            # ==============================================
            # SAME
            # ==============================================

            if item_type == "SAME":

                same_count += 1


                output.write(
                    f"[SAME] "
                    f"A:{item['old_line']} "
                    f"B:{item['new_line']} "
                    f"{item['old_text']}\n"
                )


            # ==============================================
            # CHANGED
            # ==============================================

            elif item_type == "CHANGED":

                changed_count += 1


                percent = (
                    item[
                        "similarity"
                    ]
                    * 100
                )


                output.write(
                    "\n"
                    f"[CHANGED] "
                    f"A:{item['old_line']} "
                    f"B:{item['new_line']} "
                    f"Similarity: "
                    f"{percent:.1f}%\n"
                )


                output.write(
                    f"< "
                    f"{item['old_text']}\n"
                )


                output.write(
                    f"> "
                    f"{item['new_text']}\n"
                )


            # ==============================================
            # ADDED
            # ==============================================

            elif item_type == "ADDED":

                added_count += 1


                output.write(
                    "\n"
                    f"[ADDED] "
                    f"B:{item['new_line']}\n"
                )


                output.write(
                    f"> "
                    f"{item['new_text']}\n"
                )


            # ==============================================
            # REMOVED
            # ==============================================

            elif item_type == "REMOVED":

                removed_count += 1


                output.write(
                    "\n"
                    f"[REMOVED] "
                    f"A:{item['old_line']}\n"
                )


                output.write(
                    f"< "
                    f"{item['old_text']}\n"
                )


            progress.update(
                index
            )


        # ==================================================
        # SUMMARY
        # ==================================================

        output.write(
            "\n"
            + "=" * 80
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
            f"SAME:    "
            f"{same_count}\n"
        )


        output.write(
            f"CHANGED: "
            f"{changed_count}\n"
        )


        output.write(
            f"ADDED:   "
            f"{added_count}\n"
        )


        output.write(
            f"REMOVED: "
            f"{removed_count}\n"
        )


    progress.finish()


    return {
        "same": same_count,
        "changed": changed_count,
        "added": added_count,
        "removed": removed_count
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


    file_a = sys.argv[1]
    file_b = sys.argv[2]


    # ======================================================
    # CHECK FILE A
    # ======================================================

    if not Path(
        file_a
    ).is_file():

        print(
            f"File not found: "
            f"{file_a}"
        )

        sys.exit(1)


    # ======================================================
    # CHECK FILE B
    # ======================================================

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
    # READ A
    # ======================================================

    print()
    print(
        f"Reading A: "
        f"{file_a}"
    )


    lines_a = read_file(
        file_a
    )


    print(
        f"Lines A: "
        f"{len(lines_a):,}"
    )


    # ======================================================
    # READ B
    # ======================================================

    print()
    print(
        f"Reading B: "
        f"{file_b}"
    )


    lines_b = read_file(
        file_b
    )


    print(
        f"Lines B: "
        f"{len(lines_b):,}"
    )


    # ======================================================
    # INFO
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
        f"Change threshold : "
        f"{CHANGE_THRESHOLD * 100:.0f}%"
    )


    print(
        f"Change window    : "
        f"{CHANGE_WINDOW}"
    )


    print(
        f"Length ratio     : "
        f"{MIN_LENGTH_RATIO * 100:.0f}%"
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
        lines_a,
        lines_b
    )


    compare_elapsed = (
        time.perf_counter()
        - compare_start
    )


    # ======================================================
    # REPORT
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


    # ======================================================
    # FINISHED
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
        f"SAME:    "
        f"{summary['same']:,}"
    )


    print(
        f"CHANGED: "
        f"{summary['changed']:,}"
    )


    print(
        f"ADDED:   "
        f"{summary['added']:,}"
    )


    print(
        f"REMOVED: "
        f"{summary['removed']:,}"
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