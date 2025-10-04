.. currentmodule:: sonyflake

.. _whats_new:

Changelog
============

This page keeps a detailed human friendly rendering of what's new and changed
in specific versions.

.. _v2p0p2:

v2.0.2
------

Bug Fixes
~~~~~~~~~
- Fix a bug with retrieving the private ip.

.. _v2p0p1:

v2.0.1
------

Bug Fixes
~~~~~~~~~
- Fix failing to get private IP address on macos.

.. _v2p0p0:

v2.0.0
------

Breaking Changes
~~~~~~~~~~~~~~~~

- Remove the ``AsyncSonyflake`` class. All functionality is now consolidated into the :class:`Sonyflake` class.
- Remove the ``id`` attribute from the :class:`DecomposedSonyflake` class, as it was unnecessary — the structure is intended to represent only the individual components of the ID.

New Features
~~~~~~~~~~~~

- Add :meth:`Sonyflake.next_id_async` method to the :class:`Sonyflake` class for asynchronous ID generation.
- Add new exception :class:`MachineIDCheckFailure` for explicit machine ID validation failure handling.

Miscellaneous
~~~~~~~~~~~~~

- Update documentation to reflect the new API.
- Improve error messages throughout the library for better clarity and debugging.
- Expand and improve examples to cover all supported methods of the :class:`Sonyflake` class.

.. _v1p1p0:

v1.1.0
------

New Features
~~~~~~~~~~~~

- Add support for multithreaded async environments in :class:`AsyncSonyflake`.

Miscellaneous
~~~~~~~~~~~~~

- Fix documentation for correctness and remove unnecessary content.

.. _v1p0p0:

v1.0.0
-------

- Initial Release
