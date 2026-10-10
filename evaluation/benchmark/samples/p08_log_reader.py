"""Reads application log files and counts the error lines for the daily report."""

ERROR_MARKER = " ERROR "


def read_log_lines(path):
    """Return all lines of one log file."""
    handle = open(path, encoding="utf-8")
    lines = handle.readlines()
    return lines


def count_errors(paths):
    """Count the error lines across several log files."""
    total = 0
    for path in paths:
        try:
            for line in read_log_lines(path):
                if ERROR_MARKER in line:
                    total += 1
        except:
            pass
    return total


def summary(paths):
    """Short text summary for the daily report e-mail."""
    return f"{count_errors(paths)} error line(s) in {len(paths)} file(s)"
