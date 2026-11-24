from __future__ import absolute_import, print_function, division


from decimal import Decimal

import pytest


import petl as etl
from petl.errors import FieldSelectionError
from petl.test.helpers import ieq
from petl.transform.binning import binvalues


EDGES = [0, 10, 20, 30]
LABELS = ['low', 'mid', 'high']


def test_binvalues_replaces_field_with_labels():
    table = (('id', 'x'),
             (1, 0),
             (2, 9.5),
             (3, 10),
             (4, 25))
    actual = binvalues(table, 'x', EDGES, labels=LABELS)
    expected = (('id', 'x'),
                (1, 'low'),
                (2, 'low'),
                (3, 'mid'),
                (4, 'high'))
    ieq(expected, actual)
    ieq(expected, actual)  # the view can be iterated more than once


def test_binvalues_left_closed_bins_include_last_edge():
    table = (('x',), (0,), (10,), (20,), (30,))
    actual = binvalues(table, 'x', EDGES, labels=LABELS)
    ieq((('x',), ('low',), ('mid',), ('high',), ('high',)), actual)


def test_binvalues_right_closed_bins_include_first_edge():
    table = (('x',), (0,), (10,), (10.5,), (20,), (30,))
    actual = binvalues(table, 'x', EDGES, labels=LABELS, right=True)
    expected = (('x',), ('low',), ('low',), ('mid',), ('mid',), ('high',))
    ieq(expected, actual)


def test_binvalues_default_labels_left_closed():
    table = (('x',), (0,), (15,), (30,))
    actual = binvalues(table, 'x', EDGES)
    ieq((('x',), ('[0, 10)',), ('[10, 20)',), ('[20, 30]',)), actual)


def test_binvalues_default_labels_right_closed():
    table = (('x',), (0,), (15,), (30,))
    actual = binvalues(table, 'x', EDGES, right=True)
    ieq((('x',), ('[0, 10]',), ('(10, 20]',), ('(20, 30]',)), actual)


def test_binvalues_newfield_keeps_original_values():
    table = (('id', 'x'),
             (1, 5),
             (2, 25))
    actual = binvalues(table, 'x', EDGES, labels=LABELS, newfield='x_bin')
    expected = (('id', 'x', 'x_bin'),
                (1, 5, 'low'),
                (2, 25, 'high'))
    ieq(expected, actual)


def test_binvalues_field_index():
    table = (('id', 'x'), (1, 15), (2, 5))
    ieq((('id', 'x'), (1, 'mid'), (2, 'low')),
        binvalues(table, 1, EDGES, labels=LABELS))
    ieq((('id', 'x'), (1, 'mid'), (2, 'low')),
        binvalues(table, -1, EDGES, labels=LABELS))


def test_binvalues_out_of_range_values_become_missing():
    table = (('x',), (-1,), (30.01,), (float('inf'),), (float('-inf'),))
    actual = binvalues(table, 'x', EDGES, labels=LABELS)
    ieq((('x',), (None,), (None,), (None,), (None,)), actual)


def test_binvalues_non_numeric_values_become_missing():
    table = (('x',), (None,), ('15',), (True,), (float('nan'),),
             (Decimal('NaN'),), (Decimal('sNaN'),), ([1],))
    actual = binvalues(table, 'x', EDGES, labels=LABELS, missing='n/a')
    expected = (('x',),) + (('n/a',),) * 7
    ieq(expected, actual)


def test_binvalues_decimal_values_and_edges():
    table = (('x',), (Decimal('0.15'),), (Decimal('0.5'),))
    edges = [Decimal('0'), Decimal('0.25'), Decimal('1')]
    actual = binvalues(table, 'x', edges, labels=['a', 'b'])
    ieq((('x',), ('a',), ('b',)), actual)


def test_binvalues_mixed_int_and_float():
    table = (('x',), (1,), (2.5,))
    actual = binvalues(table, 'x', [0.0, 2, 3.5], labels=['a', 'b'])
    ieq((('x',), ('a',), ('b',)), actual)


def test_binvalues_non_string_labels():
    table = (('x',), (5,), (25,))
    actual = binvalues(table, 'x', EDGES, labels=[1, 2, 3])
    ieq((('x',), (1,), (3,)), actual)


def test_binvalues_accepts_edge_and_label_iterators():
    table = (('x',), (5,), (25,))
    actual = binvalues(table, 'x', iter(EDGES), labels=iter(LABELS))
    ieq((('x',), ('low',), ('high',)), actual)
    ieq((('x',), ('low',), ('high',)), actual)


def test_binvalues_short_and_long_rows():
    table = (('id', 'x'),
             (1,),
             (2, 5, 'extra'))
    actual = binvalues(table, 'x', EDGES, labels=LABELS)
    ieq((('id', 'x'), (1,), (2, 'low', 'extra')), actual)

    actual = binvalues(table, 'x', EDGES, labels=LABELS, newfield='x_bin')
    expected = (('id', 'x', 'x_bin'),
                (1, None, None),
                (2, 5, 'low'))
    ieq(expected, actual)


def test_binvalues_header_only():
    table = (('id', 'x'),)
    ieq((('id', 'x'),), binvalues(table, 'x', EDGES))
    ieq((('id', 'x', 'b'),), binvalues(table, 'x', EDGES, newfield='b'))


def test_binvalues_empty_table():
    ieq((), binvalues((), 'x', EDGES))


def test_binvalues_unknown_field():
    table = (('id', 'x'), (1, 5))
    with pytest.raises(FieldSelectionError):
        list(binvalues(table, 'y', EDGES))
    with pytest.raises(FieldSelectionError):
        list(binvalues(table, 2, EDGES))


@pytest.mark.parametrize('edges', [
    [],
    [1],
    [0, 0, 1],
    [0, 2, 1],
    [0, float('nan')],
    [0, float('inf')],
    [0, '1'],
    [False, True],
    [0, None],
])
def test_binvalues_invalid_edges(edges):
    with pytest.raises(ValueError):
        binvalues((('x',), (1,)), 'x', edges)


@pytest.mark.parametrize('labels', [[], ['a', 'b'], ['a', 'b', 'c', 'd']])
def test_binvalues_wrong_number_of_labels(labels):
    with pytest.raises(ValueError):
        binvalues((('x',), (1,)), 'x', EDGES, labels=labels)


def test_binvalues_is_lazy():
    def rows():
        yield ('x',)
        yield (5,)
        raise AssertionError('read past the first data row')

    it = iter(binvalues(rows(), 'x', EDGES, labels=LABELS))
    assert next(it) == ('x',)
    assert next(it) == ('low',)


def test_binvalues_table_method_and_pipeline():
    table = (etl.wrap([['id', 'amount'], [1, '5'], [2, '250'], [3, 'oops']])
             .convertnumbers()
             .binvalues('amount', [0, 100, 1000], labels=['small', 'large'],
                        newfield='size'))
    expected = (('id', 'amount', 'size'),
                (1, 5, 'small'),
                (2, 250, 'large'),
                (3, 'oops', None))
    ieq(expected, table)
