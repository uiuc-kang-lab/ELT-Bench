#!/usr/bin/env python3

"""This helper command is used to print flake8 output

Usage:
    python _split_string.py <flake8_output>
    python _split_string.py <flake8_output> <previous_errors> <edit_window_start> <edit_window_end> <n_lines>

Where:
    <flake8_output> is the output of flake8
    <previous_errors> is the previous errors as a string
    <edit_window_start> is the start of the edit window
    <edit_window_end> is the end of the edit window
    <n_lines> is the number of lines added in the edit
"""

import sys
from typing import List, Tuple, Optional

class Flake8Error:
    """A class to represent a single flake8 error"""

    def __init__(self, filename, line_number, col_number, problem):
        self.filename = filename
        self.line_number = int(line_number)
        self.col_number = int(col_number)
        self.problem = problem

    @classmethod
    def from_line(cls, line):
        prefix, _sep, problem = line.partition(": ")
        filename, line_number, col_number = prefix.split(":")
        return cls(filename, int(line_number), int(col_number), problem)

    def __eq__(self, other):
        if not isinstance(other, Flake8Error):
            return NotImplemented
        return (self.filename, self.line_number, self.col_number, self.problem) == \
               (other.filename, other.line_number, other.col_number, other.problem)

    def __repr__(self):
        return "Flake8Error({!r}, {!r}, {!r}, {!r})".format(
            self.filename, self.line_number, self.col_number, self.problem
        )

def _update_previous_errors(
    previous_errors,  # type: List[Flake8Error]
    replacement_window,  # type: Tuple[int, int]
    replacement_n_lines  # type: int
):
    # type: (...) -> List[Flake8Error]
    """Update the line numbers of the previous errors to what they would be after the edit window.
    This is a helper function for `_filter_previous_errors`.

    All previous errors that are inside of the edit window should not be ignored,
    so they are removed from the previous errors list.

    Args:
        previous_errors: list of errors with old line numbers
        replacement_window: the window of the edit/lines that will be replaced
        replacement_n_lines: the number of lines that will be used to replace the text

    Returns:
        list of errors with updated line numbers
    """
    updated = []
    lines_added = replacement_n_lines - (replacement_window[1] - replacement_window[0] + 1)
    for error in previous_errors:
        if error.line_number < replacement_window[0]:
            # no need to adjust the line number
            updated.append(error)
            continue
        if replacement_window[0] <= error.line_number <= replacement_window[1]:
            # The error is within the edit window, so let's not ignore it
            # either way (we wouldn't know how to adjust the line number anyway)
            continue
        # We're out of the edit window, so we need to adjust the line number
        updated.append(Flake8Error(error.filename, error.line_number + lines_added, error.col_number, error.problem))
    return updated

def format_flake8_output(
    input_string,  # type: str
    show_line_numbers=False,  # type: bool
    previous_errors_string="",  # type: str
    replacement_window=None,  # type: Optional[Tuple[int, int]]
    replacement_n_lines=None,  # type: Optional[int]
):
    # type: (...) -> str
    """Filter flake8 output for previous errors and print it for a given file.

    Args:
        input_string: The flake8 output as a string
        show_line_numbers: Whether to show line numbers in the output
        previous_errors_string: The previous errors as a string
        replacement_window: The window of the edit (lines that will be replaced)
        replacement_n_lines: The number of lines used to replace the text

    Returns:
        The filtered flake8 output as a string
    """
    errors = [Flake8Error.from_line(line.strip()) for line in input_string.split("\n") if line.strip()]
    lines = []
    if previous_errors_string:
        assert replacement_window is not None
        assert replacement_n_lines is not None
        previous_errors = [
            Flake8Error.from_line(line.strip()) for line in previous_errors_string.split("\n") if line.strip()
        ]
        previous_errors = _update_previous_errors(previous_errors, replacement_window, replacement_n_lines)
        errors = [error for error in errors if error not in previous_errors]
    for error in errors:
        if not show_line_numbers:
            lines.append("- {}".format(error.problem))
        else:
            lines.append("- {}:{} {}".format(error.line_number, error.col_number, error.problem))
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        print(format_flake8_output(sys.argv[1]))
    elif len(sys.argv) == 6:
        window = (int(sys.argv[3]), int(sys.argv[4]))
        n_lines = int(sys.argv[5])
        print(
            format_flake8_output(
                sys.argv[1], previous_errors_string=sys.argv[2], replacement_window=window, replacement_n_lines=n_lines
            )
        )
    else:
        msg = "Invalid number of arguments. Must be 1 or 5."
        raise ValueError(msg)