"""Laugh Track: one-line crypto trading joke.

The program publishes a single joke about crypto trading life to
``$MAKEFUN_OUTPUT_DIR/entry.txt`` (``/output/entry.txt`` when the
variable is unset). The line is gate-checked before anything touches
the disk, and the file is then swapped into place with one atomic
rename, so a reader can never observe a half-written entry.
"""

import os
import sys

# The winning line. The setup ("Bought the dip") is the sentence every
# trader has said out loud; the turn ("The dip dipped") is the market
# answering the plan with the opposite; the payoff pairs a visual that
# every chart-watcher recognises ("museum of red candles") with a
# group-chat punchline that lands at the very end.
JOKE_LINE = (
    "Bought the dip. The dip dipped. Now my portfolio is a museum "
    "of red candles and my group chat charges admission to look at it."
)

LOWER_BOUND = 1
UPPER_BOUND = 200

# Standalone code points that are banned outright, whatever surrounds them.
BANNED_POINTS = ("\ufeff", "\u2028", "\u2029")

# Lone format characters that hide inside otherwise normal-looking text.
SNEAKY_FORMAT_POINTS = frozenset((0x200B, 0x200C, 0x200D, 0xFEFF, 0x00AD))


def _is_c1_control(value):
    """C1 control range U+0080..U+009F."""
    return 0x0080 <= value <= 0x009F


def _is_c0_control(value):
    """C0 controls below U+0020 (tab is already excluded by the line check)."""
    return value < 0x20


def _is_surrogate(value):
    """UTF-16 surrogate halves, which can never appear in valid UTF-8 text."""
    return 0xD800 <= value <= 0xDFFF


def _is_invisible_codepoint(value):
    """True when a code point is invisible junk rather than real content.

    Covers the C1 controls, the C0 controls, DEL, the UTF-16 surrogate
    halves (which can never appear in valid UTF-8 text), and the lone
    format characters that hide inside otherwise normal-looking text.
    """
    if _is_c1_control(value):
        return True
    if _is_c0_control(value):
        return True
    if value == 0x7F:
        return True
    if _is_surrogate(value):
        return True
    if value in SNEAKY_FORMAT_POINTS:
        return True
    return False


def _check_shape(line):
    """Reject empty, whitespace-only, over-long, or multi-line text."""
    if not isinstance(line, str):
        raise ValueError("entry must be a string")
    if not line or not line.strip():
        raise ValueError("entry must not be empty or whitespace-only")
    if len(line) < LOWER_BOUND or len(line) > UPPER_BOUND:
        raise ValueError(
            "entry must be %d-%d characters, got %d"
            % (LOWER_BOUND, UPPER_BOUND, len(line))
        )
    if "\n" in line or "\r" in line:
        raise ValueError("entry must be a single line")


def _check_banned_points(line):
    """Reject BOM and line/paragraph separators anywhere in the line."""
    for point in BANNED_POINTS:
        if point in line:
            raise ValueError(
                "entry contains forbidden character U+%04X" % ord(point)
            )


def _check_invisible_glyphs(line):
    """Reject control, format and surrogate code points in the line."""
    for glyph in line:
        if _is_invisible_codepoint(ord(glyph)):
            raise ValueError(
                "entry contains invisible character U+%04X" % ord(glyph)
            )


def check_entry(line):
    """Raise ValueError unless *line* is a single valid gate-passing line."""
    _check_shape(line)
    _check_banned_points(line)
    _check_invisible_glyphs(line)
    return line


def _clear_output_dir(path):
    """Remove every stale file inside *path*; the directory itself stays.

    Subdirectories are emptied and removed as well, so a previous run
    can never leave a stray file next to the fresh entry.
    """
    for name in os.listdir(path):
        target = os.path.join(path, name)
        if os.path.isdir(target) and not os.path.islink(target):
            for inner in os.listdir(target):
                os.unlink(os.path.join(target, inner))
            os.rmdir(target)
        else:
            os.unlink(target)


def _publish_atomically(payload, destination):
    """Write *payload* to *destination* via a same-directory staging file.

    The staging file lives next to its destination on purpose: a rename
    across filesystems would raise EXDEV, and /tmp is a different
    filesystem from a bind-mounted output directory.
    """
    out_dir = os.path.dirname(destination)
    staging = os.path.join(out_dir, ".entry.txt.tmp")
    with open(staging, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(staging, 0o644)
    os.replace(staging, destination)
    os.chmod(destination, 0o644)
    # Confirm what landed on disk is exactly what we intended to write.
    with open(destination, "rb") as stream:
        if stream.read() != payload:
            raise ValueError("read-back verification failed")


def emit_entry(line, out_dir):
    """Validate *line*, then atomically write it as entry.txt in *out_dir*."""
    check_entry(line)
    os.makedirs(out_dir, exist_ok=True)
    _clear_output_dir(out_dir)
    destination = os.path.join(out_dir, "entry.txt")
    _publish_atomically(line.encode("utf-8"), destination)
    return destination


def run():
    """Entry point: resolve the output directory and publish the joke."""
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    target = emit_entry(JOKE_LINE, out_dir)
    print("wrote %s (%d chars)" % (target, len(JOKE_LINE)))
    return 0


if __name__ == "__main__":
    sys.exit(run())
