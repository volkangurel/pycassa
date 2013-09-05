"""
A combination of utilities used internally by pycassa and utilities
available for use by others working with pycassa.

"""

import random
import uuid
import calendar
import collections

__all__ = ['convert_time_to_uuid', 'convert_uuid_to_time', 'OrderedDict']

_number_types = frozenset((int, float))

LOWEST_TIME_UUID = uuid.UUID('00000000-0000-1000-8080-808080808080')
""" The lowest possible TimeUUID, as sorted by Cassandra. """

HIGHEST_TIME_UUID = uuid.UUID('ffffffff-ffff-1fff-bf7f-7f7f7f7f7f7f')
""" The highest possible TimeUUID, as sorted by Cassandra. """

def convert_time_to_uuid(time_arg, lowest_val=True, randomize=False):
    """
    Converts a datetime or timestamp to a type 1 :class:`uuid.UUID`.

    This is to assist with getting a time slice of columns or creating
    columns when column names are ``TimeUUIDType``. Note that this is done
    automatically in most cases if name packing and value packing are
    enabled.

    Also, be careful not to rely on this when specifying a discrete
    set of columns to fetch, as the non-timestamp portions of the
    UUID will be generated randomly. This problem does not matter
    with slice arguments, however, as the non-timestamp portions
    can be set to their lowest or highest possible values.

    :param datetime:
      The time to use for the timestamp portion of the UUID.
      Expected inputs to this would either be a :class:`datetime`
      object or a timestamp with the same precision produced by
      :meth:`time.time()`. That is, sub-second precision should
      be below the decimal place.
    :type datetime: :class:`datetime` or timestamp

    :param lowest_val:
      Whether the UUID produced should be the lowest possible value
      UUID with the same timestamp as datetime or the highest possible
      value.
    :type lowest_val: bool

    :param randomize:
      Whether the clock and node bits of the UUID should be randomly
      generated.  The `lowest_val` argument will be ignored if this
      is true.
    :type randomize: bool

    :rtype: :class:`uuid.UUID`

    .. versionchanged:: 1.7.0
        Prior to 1.7.0, datetime objects were expected to be in
        local time. In 1.7.0 and beyond, naive datetimes are
        assumed to be in UTC and tz-aware objects will be
        automatically converted to UTC.

    """
    if isinstance(time_arg, uuid.UUID):
        return time_arg

    if hasattr(time_arg, 'utctimetuple'):
        seconds = int(calendar.timegm(time_arg.utctimetuple()))
        microseconds = (seconds * 1e6) + time_arg.time().microsecond
    elif type(time_arg) in _number_types:
        microseconds = int(time_arg * 1e6)
    else:
        raise ValueError('Argument for a v1 UUID column name or value was ' +
                'neither a UUID, a datetime, or a number')

    # 0x01b21dd213814000 is the number of 100-ns intervals between the
    # UUID epoch 1582-10-15 00:00:00 and the Unix epoch 1970-01-01 00:00:00.
    timestamp = int(microseconds * 10) + 0x01b21dd213814000

    time_low = timestamp & 0xffffffff
    time_mid = (timestamp >> 32) & 0xffff
    time_hi_version = (timestamp >> 48) & 0x0fff

    if randomize:
        rand_bits = random.getrandbits(8 + 8 + 48)
        clock_seq_low = rand_bits & 0xff  # 8 bits, no offset
        # keep the first two bits as 10 for the uuid variant
        clock_seq_hi_variant = 0b10000000 | (0b00111111 & ((rand_bits & 0xff00) >> 8))  # 8 bits, 8 offset
        node = (rand_bits & 0xffffffffffff0000) >> 16  # 48 bits, 16 offset
    else:
        # In the event of a timestamp tie, Cassandra compares the two
        # byte arrays directly. This is a *signed* comparison of each byte
        # in the two arrays.  So, we have to make each byte -128 or +127 for
        # this to work correctly.
        #
        # For the clock_seq_hi_variant, we don't get to pick the two most
        # significant bits (they're always 10), so we are dealing with a
        # positive byte range for this particular byte.
        if lowest_val:
            # Make the lowest value UUID with the same timestamp
            clock_seq_low = 0x80
            clock_seq_hi_variant = 0 & 0x80 # The two most significant bits
                                             # will be 10 for the variant
            node = 0x808080808080 # 48 bits
        else:
            # Make the highest value UUID with the same timestamp

            # uuid timestamps have 100ns precision, while the timestamp
            # we have only has microsecond precision; to create the highest
            # uuid for the same microsecond, add 900ns
            timestamp = int(timestamp + 9)

            clock_seq_low = 0x7f
            clock_seq_hi_variant = 0xbf # The two most significant bits will
                                         # 10 for the variant
            node = 0x7f7f7f7f7f7f # 48 bits
    return uuid.UUID(fields=(time_low, time_mid, time_hi_version,
                        clock_seq_hi_variant, clock_seq_low, node), version=1)

def convert_uuid_to_time(uuid_arg):
    """
    Converts a version 1 :class:`uuid.UUID` to a timestamp with the same precision
    as :meth:`time.time()` returns.  This is useful for examining the
    results of queries returning a v1 :class:`~uuid.UUID`.

    :param uuid_arg: a version 1 :class:`~uuid.UUID`

    :rtype: timestamp

    """
    ts = uuid_arg.get_time()
    return (ts - 0x01b21dd213814000)/1e7

# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010 Michael Bayer mike_mp@zzzcomputing.com
#
# The 'as_interface' method is part of SQLAlchemy and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

import operator

def as_interface(obj, cls=None, methods=None, required=None):
    """Ensure basic interface compliance for an instance or dict of callables.

    Checks that ``obj`` implements public methods of ``cls`` or has members
    listed in ``methods``.  If ``required`` is not supplied, implementing at
    least one interface method is sufficient.  Methods present on ``obj`` that
    are not in the interface are ignored.

    If ``obj`` is a dict and ``dict`` does not meet the interface
    requirements, the keys of the dictionary are inspected. Keys present in
    ``obj`` that are not in the interface will raise TypeErrors.

    Raises TypeError if ``obj`` does not meet the interface criteria.

    In all passing cases, an object with callable members is returned.  In the
    simple case, ``obj`` is returned as-is; if dict processing kicks in then
    an anonymous class is returned.

    obj
      A type, instance, or dictionary of callables.
    cls
      Optional, a type.  All public methods of cls are considered the
      interface.  An ``obj`` instance of cls will always pass, ignoring
      ``required``..
    methods
      Optional, a sequence of method names to consider as the interface.
    required
      Optional, a sequence of mandatory implementations. If omitted, an
      ``obj`` that provides at least one interface method is considered
      sufficient.  As a convenience, required may be a type, in which case
      all public methods of the type are required.

    """
    if not cls and not methods:
        raise TypeError('a class or collection of method names are required')

    if isinstance(cls, type) and isinstance(obj, cls):
        return obj

    interface = set(methods or [m for m in dir(cls) if not m.startswith('_')])
    implemented = set(dir(obj))

    complies = operator.ge
    if isinstance(required, type):
        required = interface
    elif not required:
        required = set()
        complies = operator.gt
    else:
        required = set(required)

    if complies(implemented.intersection(interface), required):
        return obj

    # No dict duck typing here.
    if not type(obj) is dict:
        qualifier = complies is operator.gt and 'any of' or 'all of'
        raise TypeError("%r does not implement %s: %s" % (
            obj, qualifier, ', '.join(interface)))

    class AnonymousInterface(object):
        """A callable-holding shell."""

    if cls:
        AnonymousInterface.__name__ = 'Anonymous' + cls.__name__
    found = set()

    for method, impl in dictlike_iteritems(obj):
        if method not in interface:
            raise TypeError("%r: unknown in this interface" % method)
        if not isinstance(impl, collections.Callable):
            raise TypeError("%r=%r is not callable" % (method, impl))
        setattr(AnonymousInterface, method, staticmethod(impl))
        found.add(method)

    if complies(found, required):
        return AnonymousInterface

    raise TypeError("dictionary does not contain required keys %s" %
                    ', '.join(required - found))
