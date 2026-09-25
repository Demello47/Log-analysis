import sys
import difflib
from pathlib import Path


# ==========================================================
# SETTINGS
# ==========================================================

# Насколько две строки должны быть похожи,
# чтобы считать их CHANGED, а не REMOVED + ADDED.
#
# 0.0 = совсем не похожи
# 1.0 = полностью одинаковые
CHANGE_THRESHOLD = 0.55


# ==========================================================
# READ FILE
# ==========================================================

def read_file(path):

    with open(
        path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        return [
            line.rstrip("\r\n")
            for line in f
        ]


# ==========================================================
# LINE SIMILARITY
# ==========================================================

def similarity(line_a, line_b):

    return difflib.SequenceMatcher(
        None,
        line_a,
        line_b,
        autojunk=False
    ).ratio()


# ==========================================================
# TRY TO PAIR REMOVED + ADDED LINES
# AS CHANGED
# ==========================================================

def pair_changed_lines(
    removed,
    added
):

    results = []

    used_added = set()


    for old_line_num, old_text in removed:

        best_index = None
        best_score = 0.0


        for index, (
            new_line_num,
            new_text
        ) in enumerate(added):

            if index in used_added:
                continue


            score = similarity(
                old_text,
                new_text
            )


            if score > best_score:

                best_score = score
                best_index = index


        # --------------------------------------------------
        # Similar enough -> CHANGED
        # --------------------------------------------------

        if (
            best_index is not None
            and best_score >= CHANGE_THRESHOLD
        ):

            new_line_num, new_text = added[
                best_index
            ]

            used_added.add(
                best_index
            )


            results.append({

                "type": "CHANGED",

                "old_line": old_line_num,
                "new_line": new_line_num,

                "old_text": old_text,
                "new_text": new_text,

                "similarity": best_score
            })


        # --------------------------------------------------
        # No matching new line -> REMOVED
        # --------------------------------------------------

        else:

            results.append({

                "type": "REMOVED",

                "old_line": old_line_num,
                "new_line": None,

                "old_text": old_text,
                "new_text": None,

                "similarity": None
            })


    # ------------------------------------------------------
    # Remaining added lines
    # ------------------------------------------------------

    for index, (
        new_line_num,
        new_text
    ) in enumerate(added):

        if index in used_added:
            continue


        results.append({

            "type": "ADDED",

            "old_line": None,
            "new_line": new_line_num,

            "old_text": None,
            "new_text": new_text,

            "similarity": None
        })


    return results


# ==========================================================
# COMPARE
# ==========================================================

def compare_files(
    lines_a,
    lines_b
):

    matcher = difflib.SequenceMatcher(
        None,
        lines_a,
        lines_b,
        autojunk=False
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

            for offset in range(
                a_end - a_start
            ):

                old_index = (
                    a_start + offset
                )

                new_index = (
                    b_start + offset
                )


                results.append({

                    "type": "SAME",

                    "old_line":
                        old_index + 1,

                    "new_line":
                        new_index + 1,

                    "old_text":
                        lines_a[old_index],

                    "new_text":
                        lines_b[new_index],

                    "similarity":
                        1.0
                })


        # ==================================================
        # REMOVED
        # ==================================================

        elif tag == "delete":

            for index in range(
                a_start,
                a_end
            ):

                results.append({

                    "type": "REMOVED",

                    "old_line":
                        index + 1,

                    "new_line":
                        None,

                    "old_text":
                        lines_a[index],

                    "new_text":
                        None,

                    "similarity":
                        None
                })


        # ==================================================
        # ADDED
        # ==================================================

        elif tag == "insert":

            for index in range(
                b_start,
                b_end
            ):

                results.append({

                    "type": "ADDED",

                    "old_line":
                        None,

                    "new_line":
                        index + 1,

                    "old_text":
                        None,

                    "new_text":
                        lines_b[index],

                    "similarity":
                        None
                })


        # ==================================================
        # REPLACE
        #
        # Could contain:
        #
        # CHANGED
        # REMOVED
        # ADDED
        # ==================================================

        elif tag == "replace":

            removed = [

                (
                    index + 1,
                    lines_a[index]
                )

                for index in range(
                    a_start,
                    a_end
                )
            ]


            added = [

                (
                    index + 1,
                    lines_b[index]
                )

                for index in range(
                    b_start,
                    b_end
                )
            ]


            block_results = pair_changed_lines(
                removed,
                added
            )


            results.extend(
                block_results
            )


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

    same_count = 0
    changed_count = 0
    added_count = 0
    removed_count = 0


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
            "=" * 80 + "\n\n"
        )


        for item in results:

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
                    item["similarity"]
                    * 100
                )

                output.write(
                    f"\n[CHANGED] "
                    f"A:{item['old_line']} "
                    f"B:{item['new_line']} "
                    f"Similarity: "
                    f"{percent:.1f}%\n"
                )

                output.write(
                    f"< {item['old_text']}\n"
                )

                output.write(
                    f"> {item['new_text']}\n"
                )


            # ==============================================
            # ADDED
            # ==============================================

            elif item_type == "ADDED":

                added_count += 1

                output.write(
                    f"\n[ADDED] "
                    f"B:{item['new_line']}\n"
                )

                output.write(
                    f"> {item['new_text']}\n"
                )


            # ==============================================
            # REMOVED
            # ==============================================

            elif item_type == "REMOVED":

                removed_count += 1

                output.write(
                    f"\n[REMOVED] "
                    f"A:{item['old_line']}\n"
                )

                output.write(
                    f"< {item['old_text']}\n"
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
            f"SAME:    {same_count}\n"
        )

        output.write(
            f"CHANGED: {changed_count}\n"
        )

        output.write(
            f"ADDED:   {added_count}\n"
        )

        output.write(
            f"REMOVED: {removed_count}\n"
        )


# ==========================================================
# MAIN
# ==========================================================

def main():

    if len(sys.argv) != 3:

        print(
            "Usage:"
        )

        print(
            "python.exe compare_engine.py "
            "file_A.log file_B.log"
        )

        sys.exit(1)


    file_a = sys.argv[1]
    file_b = sys.argv[2]


    # ======================================================
    # CHECK FILES
    # ======================================================

    if not Path(
        file_a
    ).is_file():

        print(
            f"File not found: {file_a}"
        )

        sys.exit(1)


    if not Path(
        file_b
    ).is_file():

        print(
            f"File not found: {file_b}"
        )

        sys.exit(1)


    print(
        f"Reading: {file_a}"
    )

    lines_a = read_file(
        file_a
    )


    print(
        f"Reading: {file_b}"
    )

    lines_b = read_file(
        file_b
    )


    print()

    print(
        f"File A: {len(lines_a)} lines"
    )

    print(
        f"File B: {len(lines_b)} lines"
    )


    print()

    print(
        "Comparing..."
    )


    results = compare_files(
        lines_a,
        lines_b
    )


    output_file = (
        "compare_results.txt"
    )


    write_report(
        results,
        file_a,
        file_b,
        output_file
    )


    print(
        "Comparison completed."
    )

    print(
        f"Results: {output_file}"
    )


# ==========================================================
# START
# ==========================================================

if __name__ == "__main__":
    main()