#!/usr/bin/env bash
# The workspace of rc-28: the base on main, pull request #1 on phase/P1.
. "$(dirname "$0")/../fixture.sh"

rc_base 'tables' 'One cell format' '`render`, `render_markdown`, `render_csv` '\
'and `render_html` share one cell format and one number rule instead of '\
'four copies of each; their output stays the same.' \
  '`table.py`, `tests/`' \
  'each of the four functions gives the same output as before for every '\
'table (every row as long as the headers); the cell format and the number rule are written once'
cat > 'table.py' <<'EOF'
"""A table (a list of headers and rows of cells of the same length) as plain text, Markdown,
CSV or HTML. A cell is None, a bool, an int, a float or anything else, shown as its str."""


def render(headers, rows):
    """Plain text: columns padded to their widest cell, two spaces apart, numbers right-aligned,
    a line of dashes under the headers, no trailing spaces."""
    texts = []
    for row in rows:
        cells = []
        for cell in row:
            if cell is None:
                cells.append("")
            elif isinstance(cell, bool):
                cells.append("yes" if cell else "no")
            elif isinstance(cell, float):
                cells.append("%.2f" % cell)
            else:
                cells.append(str(cell))
        texts.append(cells)
    widths = [len(str(header)) for header in headers]
    for cells in texts:
        for index, text in enumerate(cells):
            if len(text) > widths[index]:
                widths[index] = len(text)
    lines = ["  ".join(str(header).ljust(widths[index])
                       for index, header in enumerate(headers)).rstrip()]
    lines.append("  ".join("-" * width for width in widths))
    for row, cells in zip(rows, texts):
        parts = []
        for index, text in enumerate(cells):
            cell = row[index]
            if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                parts.append(text.rjust(widths[index]))
            else:
                parts.append(text.ljust(widths[index]))
        lines.append("  ".join(parts).rstrip())
    return "\n".join(lines)


def render_markdown(headers, rows):
    """A Markdown table of the same cells, `|` escaped; a column whose cells are all numbers
    (and that has at least one) is right-aligned."""
    texts = []
    for row in rows:
        cells = []
        for cell in row:
            if cell is None:
                cells.append("")
            elif isinstance(cell, bool):
                cells.append("yes" if cell else "no")
            elif isinstance(cell, float):
                cells.append("%.2f" % cell)
            else:
                cells.append(str(cell))
        texts.append(cells)
    aligns = []
    for index in range(len(headers)):
        column = [row[index] for row in rows]
        numbers = [cell for cell in column
                   if isinstance(cell, (int, float)) and not isinstance(cell, bool)]
        aligns.append("--:" if column and len(numbers) == len(column) else "---")
    lines = ["| " + " | ".join(str(header).replace("|", "\\|") for header in headers) + " |"]
    lines.append("|" + "|".join(aligns) + "|")
    for cells in texts:
        lines.append("| " + " | ".join(text.replace("|", "\\|") for text in cells) + " |")
    return "\n".join(lines)


def render_csv(headers, rows):
    """CSV of the same cells: a cell with a comma, a quote or a line break in quotes, its quotes
    doubled; lines end with \\r\\n."""
    texts = [[str(header) for header in headers]]
    for row in rows:
        cells = []
        for cell in row:
            if cell is None:
                cells.append("")
            elif isinstance(cell, bool):
                cells.append("yes" if cell else "no")
            elif isinstance(cell, float):
                cells.append("%.2f" % cell)
            else:
                cells.append(str(cell))
        texts.append(cells)
    lines = []
    for cells in texts:
        quoted = []
        for text in cells:
            if any(char in text for char in ',"\r\n'):
                quoted.append('"' + text.replace('"', '""') + '"')
            else:
                quoted.append(text)
        lines.append(",".join(quoted))
    return "".join(line + "\r\n" for line in lines)


def render_html(headers, rows):
    """An HTML table of the same cells, `&`, `<` and `>` escaped; a number cell has
    class="num"."""
    texts = []
    for row in rows:
        cells = []
        for cell in row:
            if cell is None:
                cells.append("")
            elif isinstance(cell, bool):
                cells.append("yes" if cell else "no")
            elif isinstance(cell, float):
                cells.append("%.2f" % cell)
            else:
                cells.append(str(cell))
        texts.append(cells)
    heads = []
    for header in headers:
        text = str(header).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        heads.append("<th>%s</th>" % text)
    lines = ["<table>", "<tr>" + "".join(heads) + "</tr>"]
    for row, cells in zip(rows, texts):
        parts = []
        for cell, text in zip(row, cells):
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                parts.append('<td class="num">%s</td>' % text)
            else:
                parts.append("<td>%s</td>" % text)
        lines.append("<tr>" + "".join(parts) + "</tr>")
    lines.append("</table>")
    return "\n".join(lines)
EOF
cat > 'tests/test_table.py' <<'EOF'
import unittest

from table import render, render_csv, render_html, render_markdown

HEADERS = ["name", "qty", "price", "ok"]
ROWS = [["pen", 3, 1.5, True], ["ink|blue", 12, None, False], ['a "b", c', 0, 10.0, None]]


class RenderTest(unittest.TestCase):
    def test_render(self):
        self.assertEqual(render(HEADERS, ROWS).split("\n"), [
            "name      qty  price  ok",
            "--------  ---  -----  ---",
            "pen         3   1.50  yes",
            "ink|blue   12         no",
            'a "b", c    0  10.00'])

    def test_markdown(self):
        self.assertEqual(render_markdown(HEADERS, ROWS).split("\n"), [
            "| name | qty | price | ok |",
            "|---|--:|---|---|",
            "| pen | 3 | 1.50 | yes |",
            "| ink\\|blue | 12 |  | no |",
            '| a "b", c | 0 | 10.00 |  |'])
        self.assertEqual(render_markdown(["n"], []), "| n |\n|---|")

    def test_csv(self):
        self.assertEqual(render_csv(HEADERS, ROWS),
                         'name,qty,price,ok\r\npen,3,1.50,yes\r\nink|blue,12,,no\r\n'
                         '"a ""b"", c",0,10.00,\r\n')
        self.assertEqual(render_csv(["a"], [["x\ny"]]), 'a\r\n"x\ny"\r\n')

    def test_html(self):
        self.assertEqual(render_html(["a<b", "n"], [["x & y", 2], [None, 1.5]]).split("\n"), [
            "<table>", "<tr><th>a&lt;b</th><th>n</th></tr>",
            '<tr><td>x &amp; y</td><td class="num">2</td></tr>',
            '<tr><td></td><td class="num">1.50</td></tr>', "</table>"])
EOF
rc_commit 00 'Base: tables'
rc_branch
cat > 'table.py' <<'EOF'
"""A table (a list of headers and rows of cells of the same length) as plain text, Markdown,
CSV or HTML. A cell is None, a bool, an int, a float or anything else, shown as its str."""


def cell_text(cell):
    """How every rendering shows a cell: None empty, a bool as yes or no, a float with two
    decimals, anything else as its str."""
    if cell is None:
        return ""
    if isinstance(cell, bool):
        return "yes" if cell else "no"
    if isinstance(cell, float):
        return "%.2f" % cell
    return str(cell)


def is_number(cell):
    """Whether a cell is shown as a number (right-aligned): an int or a float, not a bool."""
    return isinstance(cell, (int, float)) and not isinstance(cell, bool)


def _texts(rows):
    return [[cell_text(cell) for cell in row] for row in rows]


def render(headers, rows):
    """Plain text: columns padded to their widest cell, two spaces apart, numbers right-aligned,
    a line of dashes under the headers, no trailing spaces."""
    texts = _texts(rows)
    widths = [max([len(str(header))] + [len(cells[index]) for cells in texts])
              for index, header in enumerate(headers)]
    lines = ["  ".join(str(header).ljust(width)
                       for header, width in zip(headers, widths)).rstrip(),
             "  ".join("-" * width for width in widths)]
    for row, cells in zip(rows, texts):
        lines.append("  ".join(text.rjust(width) if is_number(cell) else text.ljust(width)
                               for cell, text, width in zip(row, cells, widths)).rstrip())
    return "\n".join(lines)


def render_markdown(headers, rows):
    """A Markdown table of the same cells, `|` escaped; a column whose cells are all numbers
    (and that has at least one) is right-aligned."""
    aligns = ["--:" if rows and all(is_number(row[index]) for row in rows) else "---"
              for index in range(len(headers))]
    lines = ["| " + " | ".join(str(header).replace("|", "\\|") for header in headers) + " |",
             "|" + "|".join(aligns) + "|"]
    for cells in _texts(rows):
        lines.append("| " + " | ".join(text.replace("|", "\\|") for text in cells) + " |")
    return "\n".join(lines)


def _csv_field(text):
    if any(char in text for char in ',"\r\n'):
        return '"' + text.replace('"', '""') + '"'
    return text


def render_csv(headers, rows):
    """CSV of the same cells: a cell with a comma, a quote or a line break in quotes, its quotes
    doubled; lines end with \\r\\n."""
    texts = [[str(header) for header in headers]] + _texts(rows)
    return "".join(",".join(_csv_field(text) for text in cells) + "\r\n" for cells in texts)


def _html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(headers, rows):
    """An HTML table of the same cells, `&`, `<` and `>` escaped; a number cell has
    class="num"."""
    lines = ["<table>",
             "<tr>" + "".join("<th>%s</th>" % _html(str(header)) for header in headers) + "</tr>"]
    for row, cells in zip(rows, _texts(rows)):
        lines.append("<tr>" + "".join(
            ('<td class="num">%s</td>' if is_number(cell) else "<td>%s</td>") % _html(text)
            for cell, text in zip(row, cells)) + "</tr>")
    lines.append("</table>")
    return "\n".join(lines)
EOF
cat > 'tests/test_table.py' <<'EOF'
import unittest

from table import (cell_text, is_number, render, render_csv, render_html,
                   render_markdown)

HEADERS = ["name", "qty", "price", "ok"]
ROWS = [["pen", 3, 1.5, True], ["ink|blue", 12, None, False], ['a "b", c', 0, 10.0, None]]


class CellTest(unittest.TestCase):
    def test_cell_text(self):
        self.assertEqual([cell_text(c) for c in (None, True, False, 2, 2.5, 1e3, "x")],
                         ["", "yes", "no", "2", "2.50", "1000.00", "x"])

    def test_is_number(self):
        self.assertEqual([is_number(c) for c in (1, 1.5, True, None, "1")],
                         [True, True, False, False, False])


class RenderTest(unittest.TestCase):
    def test_render(self):
        self.assertEqual(render(HEADERS, ROWS).split("\n"), [
            "name      qty  price  ok",
            "--------  ---  -----  ---",
            "pen         3   1.50  yes",
            "ink|blue   12         no",
            'a "b", c    0  10.00'])
        self.assertEqual(render(["a", "b"], []), "a  b\n-  -")

    def test_markdown(self):
        self.assertEqual(render_markdown(HEADERS, ROWS).split("\n"), [
            "| name | qty | price | ok |",
            "|---|--:|---|---|",
            "| pen | 3 | 1.50 | yes |",
            "| ink\\|blue | 12 |  | no |",
            '| a "b", c | 0 | 10.00 |  |'])
        self.assertEqual(render_markdown(["n"], []), "| n |\n|---|")

    def test_csv(self):
        self.assertEqual(render_csv(HEADERS, ROWS),
                         'name,qty,price,ok\r\npen,3,1.50,yes\r\nink|blue,12,,no\r\n'
                         '"a ""b"", c",0,10.00,\r\n')
        self.assertEqual(render_csv(["a"], [["x\ny"]]), 'a\r\n"x\ny"\r\n')
        self.assertEqual(render_csv(["a,b"], []), '"a,b"\r\n')

    def test_html(self):
        self.assertEqual(render_html(["a<b", "n"], [["x & y", 2], [None, 1.5]]).split("\n"), [
            "<table>", "<tr><th>a&lt;b</th><th>n</th></tr>",
            '<tr><td>x &amp; y</td><td class="num">2</td></tr>',
            '<tr><td></td><td class="num">1.50</td></tr>', "</table>"])
        self.assertEqual(render_html(["n"], []), "<table>\n<tr><th>n</th></tr>\n</table>")
EOF
rc_mark_done
rc_commit 10 'P1: One cell format'
rc_publish
