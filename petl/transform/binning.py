from __future__ import absolute_import, print_function, division


import math
from bisect import bisect_left, bisect_right


from petl.compat import numeric_types
from petl.util.base import Table, asindices


def binvalues(table, field, edges, labels=None, newfield=None, right=False,
              missing=None):
    """
    Assign the numeric values of a field to bins defined by `edges`, e.g.,
    to turn ages or amounts into categories for reporting::

        >>> import petl as etl
        >>> table1 = [['id', 'age'],
        ...           [1, 4],
        ...           [2, 17],
        ...           [3, 18],
        ...           [4, 65],
        ...           [5, 120]]
        >>> table2 = etl.binvalues(table1, 'age', [0, 18, 65, 120],
        ...                        labels=['child', 'adult', 'senior'])
        >>> table2
        +----+----------+
        | id | age      |
        +====+==========+
        |  1 | 'child'  |
        +----+----------+
        |  2 | 'child'  |
        +----+----------+
        |  3 | 'adult'  |
        +----+----------+
        |  4 | 'senior' |
        +----+----------+
        |  5 | 'senior' |
        +----+----------+

    The `edges` must be a sequence of at least two finite numbers in strictly
    increasing order. Each pair of consecutive edges defines one bin. By
    default bins include their left edge and exclude their right edge, e.g.,
    ``[0, 18)``. Use ``right=True`` to include the right edge instead, e.g.,
    ``(0, 18]``. The two outermost edges are always included, so every value
    from ``edges[0]`` to ``edges[-1]`` is assigned to a bin.

    If `labels` is not given, each bin is labelled with its interval::

        >>> table3 = etl.binvalues(table1, 'age', [0, 18, 65, 120],
        ...                        newfield='age_group', right=True)
        >>> table3.values('age_group').list()
        ['[0, 18]', '[0, 18]', '[0, 18]', '(18, 65]', '(65, 120]']

    The number of `labels` must be one less than the number of `edges`.

    The `field` may be given as a field name or a column index. By default the
    bin labels replace the values of `field`. Use `newfield` to keep the
    original values and add the labels under a new field instead. Rows
    shorter than the header are then padded with ``None`` and rows longer
    than the header are truncated, so the labels stay under `newfield`.

    Values outside the range of the edges, and values that are not numbers,
    including ``None``, booleans, strings and NaN, are replaced by `missing`.
    Values read from text files are strings, so convert them first, e.g.,
    with :func:`petl.transform.conversions.convertnumbers`.

    Values are processed one row at a time, so the table is not loaded into
    memory.

    """

    return BinValuesView(table, field, edges, labels=labels,
                         newfield=newfield, right=right, missing=missing)


Table.binvalues = binvalues


class BinValuesView(Table):
    """View returned by :func:`binvalues`."""

    def __init__(self, source, field, edges, labels=None, newfield=None,
                 right=False, missing=None):
        self.source = source
        self.field = field
        self.edges = _checkedges(edges)
        self.labels = _checklabels(labels, self.edges, right)
        self.newfield = newfield
        self.right = right
        self.missing = missing

    def __iter__(self):
        return iterbinvalues(self.source, self.field, self.edges, self.labels,
                             self.newfield, self.right, self.missing)


def _isnumber(value):
    if isinstance(value, bool) or not isinstance(value, numeric_types):
        return False
    try:
        return not math.isnan(value)
    except (TypeError, ValueError, OverflowError):
        return False


def _checkedges(edges):
    edges = list(edges)
    if len(edges) < 2:
        raise ValueError('at least two edges are required, found %r' % edges)
    for edge in edges:
        if not _isnumber(edge) or math.isinf(edge):
            raise ValueError('edges must be finite numbers, found %r' % edge)
    for lower, upper in zip(edges, edges[1:]):
        if not lower < upper:
            raise ValueError('edges must be strictly increasing, found %r '
                             'followed by %r' % (lower, upper))
    return edges


def _checklabels(labels, edges, right):
    nbins = len(edges) - 1
    if labels is None:
        return _defaultlabels(edges, right)
    labels = list(labels)
    if len(labels) != nbins:
        raise ValueError('expected %s labels for %s edges, found %s'
                         % (nbins, len(edges), len(labels)))
    return labels


def _defaultlabels(edges, right):
    labels = []
    last = len(edges) - 2
    for i, (lower, upper) in enumerate(zip(edges, edges[1:])):
        if right:
            opening = '[' if i == 0 else '('
            closing = ']'
        else:
            opening = '['
            closing = ']' if i == last else ')'
        labels.append('%s%s, %s%s' % (opening, lower, upper, closing))
    return labels


def _binindex(value, edges, right):
    """Return the index of the bin containing `value`, or None."""
    if value < edges[0] or value > edges[-1]:
        return None
    if right:
        if value == edges[0]:
            return 0
        return bisect_left(edges, value) - 1
    if value == edges[-1]:
        return len(edges) - 2
    return bisect_right(edges, value) - 1


def iterbinvalues(source, field, edges, labels, newfield, right, missing):
    it = iter(source)
    try:
        header = next(it)
    except StopIteration:
        return

    idx = asindices(header, field)[0]

    if newfield is None:
        yield tuple(header)
    else:
        yield tuple(header) + (newfield,)

    width = len(header)
    for row in it:
        row = list(row)
        value = row[idx] if idx < len(row) else None
        label = missing
        if _isnumber(value):
            i = _binindex(value, edges, right)
            if i is not None:
                label = labels[i]

        if newfield is None:
            if idx < len(row):
                row[idx] = label
        else:
            # keep the label aligned with the new field in short or long rows
            row = row[:width]
            row.extend([None] * (width - len(row)))
            row.append(label)
        yield tuple(row)
