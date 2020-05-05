"""Contain  handlers of PDB information."""
import contextlib
import functools
import re
import string
import traceback
import urllib.request
from abc import ABC, abstractmethod
from collections import namedtuple
from multiprocessing.pool import ThreadPool

import numpy as np

from idpconfgen import Path, log
from idpconfgen.core import count_string_formatters
from idpconfgen.core import exceptions as EXCPTS
from idpconfgen.libs import libtimer
from idpconfgen.logger import S, T


PDBField = namedtuple('PDBField', ['slice', 'col'])

# ATOM and HETATM fields


def format_atom_name(atom, element):
    #a = atom.strip()
    if element in ('C', 'N', 'O', 'S'):
        if len(atom) < 4:
            return ' {:<3s}'.format(atom)
        else:
            return '{:<4s}'.format(atom)
    elif len(atom) == 2:
        return '{:<2s}  '.format(atom)
    else:
        _ = f'Could not format this atom:type {atom}:{element}'
        raise EXCPTS.PDBFormatError(_)


def format_chainid(chain):
    """
    Format chain identifier to one letter.

    This is required to receive chain IDs from mmCIF files, which
    may have more than one letter.
    """
    return chain.strip()[0]


atom_record = PDBField(slice(0, 6), 0)
atom_serial = PDBField(slice(6, 11), 1)
atom_name = PDBField(slice(12, 16), 2)
atom_altLoc = PDBField(slice(16, 17), 3)
atom_resName = PDBField(slice(17, 20), 4)
atom_chainID = PDBField(slice(21, 22), 5)
atom_resSeq = PDBField(slice(22, 26), 6)
atom_iCode = PDBField(slice(26, 27), 7)
atom_x = PDBField(slice(30, 38), 8)
atom_y = PDBField(slice(38, 46), 9)
atom_z = PDBField(slice(46, 54), 10)
atom_occ = PDBField(slice(54, 60), 11)
atom_temp = PDBField(slice(60, 66), 12)
atom_segid = PDBField(slice(72, 76), 13)
atom_element = PDBField(slice(76, 78), 14)
atom_model = PDBField(slice(78, 80), 15)

# order matters
atom_slicers = [
    atom_record.slice,
    atom_serial.slice,
    atom_name.slice,
    atom_altLoc.slice,
    atom_resName.slice,
    atom_chainID.slice,
    atom_resSeq.slice,
    atom_iCode.slice,
    atom_x.slice,
    atom_y.slice,
    atom_z.slice,
    atom_occ.slice,
    atom_temp.slice,
    atom_segid.slice,
    atom_element.slice,
    atom_model.slice,
    ]


atom_line_formatter = (
        "{:6s}"
        "{:5d} "
        "{}"
        "{:1s}"
        "{:3s} "
        "{:1s}"
        "{:4d}"
        "{:1s}   "
        "{:8.3f}"
        "{:8.3f}"
        "{:8.3f}"
        "{:6.2f}"
        "{:6.2f}      "
        "{:<4s}"
        "{:>2s}"
        "{:2s}"
        )

# functions to apply to each format field in atom line string
atom_format_funcs = [
    #str, int, format_atom_name, str, str,
    str, int, str.strip, str, str,
    format_chainid, int, str, float, float,
    float, float, float, str, str,
    str]


def is_pdb(datastr):
    """Detect if `datastr` if a PDB format v3 file."""
    assert isinstance(datastr, str), \
        f'`datastr` is not str: {type(datastr)} instead'
    return bool(datastr.count('\nATOM ') > 0)



class PDBIDFactory:
    r"""
    Parse input for PDBID instatiation.

    Parameters
    ----------
    name : str or Path
        The code name or ID that identified the PDB.
        Possible formats:

            - XXXX
            - XXXXC\*
            - XXXX_C\*
            - \*.pdb

        where XXXX is the PDBID code, C is the chain ID and * means
        any number of characters. PDB and chaind ID codes are any digits,
        lower and upper case letters.

    Returns
    -------
    :class:`PDBID` object.

    """

    rgx_XXXX = re.compile(r'^[0-9a-zA-Z]{4}(\s|$)')
    rgx_XXXXC = re.compile(r'^[0-9a-zA-Z]{5,}(\s|$)')
    rgx_XXXX_C = re.compile(r'^[0-9a-zA-Z]{4}_[0-9a-zA-Z]+(\s|$)')

    def __new__(cls, name):
        """Construct class."""
        if isinstance(name, PDBID):
            return name

        namep = Path(name)
        if namep.suffix == '.pdb':
            name = namep.stem

        # where XXXX is the PDBID and C the chain ID
        pdb_filename_regex = {
            cls.rgx_XXXX: cls._parse_XXXX,
            cls.rgx_XXXXC: cls._parse_XXXXC,
            cls.rgx_XXXX_C: cls._parse_XXXX_C,
            }

        for regex, parser in pdb_filename_regex.items():
            if regex.search(str(name)):  # in case Path obj
                return PDBID(*parser(name))
        else:
            emsg = f"PDB code format not valid: {name}. No regex matches."
            raise EXCPTS.PDBIDFactoryError(emsg)

    @staticmethod
    def _parse_XXXX(pdbid):
        return pdbid[:4], None

    @staticmethod
    def _parse_XXXXC(pdbid):
        pdbinfo = pdbid.split()[0]
        return pdbinfo[:4], pdbinfo[4:]

    @staticmethod
    def _parse_XXXX_C(pdbid):
        pdbid, chainid = pdbid.split()[0].split('_')
        return pdbid, chainid


class PDBList:
    """
    List of PDBID objects.

    Parameters
    ----------
    pdb_names : obj:iterator
        An iterator containing the PDB names.
        PDB names can be in the form accepted by PDBIDFactory or
        PDBID objects.
    """

    def __new__(cls, pdb_names):  # noqa: D102

        try:
            if isinstance(pdb_names, cls):
                return pdb_names
            else:
                return super().__new__(cls)
        except IndexError:
            return super().__new__(cls)

    def __init__(self, pdb_names):
        valid_pdb_names = filter(
            # str() because may receive Paths
            lambda x: not str(x).startswith('#'),
            pdb_names,
            )
        self.set = set(PDBIDFactory(element) for element in valid_pdb_names)

    def __repr__(self):
        return '{}(\n    {})\n'.format(
            self.__class__.__name__,
            ',\n    '.join(repr(x) for x in self),
            )

    def __str__(self):
        return '{} with {} elements'.format(
            self.__class__.__name__,
            len(self),
            )

    def __eq__(self, other):
        try:
            return self.set == other.set
        except AttributeError:
            return self.set == other

    def __iter__(self):
        return iter(self.to_tuple())

    def __getitem__(self, index):
        return self.to_tuple()[index]

    def __len__(self):
        return len(self.set)

    def to_tuple(self):
        """Convert PDBList to sorted tuple."""
        return tuple(sorted(self.set))

    def difference(self, other):
        """
        Difference between self and other.

        Returns
        -------
        PDBList
        """
        return PDBList(tuple(self.set.difference(other.set)))

    def write(self, filename='PDBIDs.list'):
        """
        Write to a file the PDBIDs in the PDBList.

        Parameters
        ----------
        filename : str, optional
            The output file name.
        """
        with open(filename, 'w') as fh:
            fh.write('\n'.join(str(pdbid) for pdbid in self.to_tuple()))

        log.info(S(f'PDBIDs written to {filename}'))


@functools.total_ordering
class PDBID:
    """
    PDB object identifier.

    Identifies unique downloadable/stored units.

    In the current implmentation each unit is one PDB chain,
    which is identified by the PDBID and its chain identifier.

    Parameters
    ----------
    name : obj:`str`
        The PDBID, for example: 1ABC

    chain : obj:`str`
        The chain identifier.
        Defaults to None.

    Attributes
    ----------
    name:
        The four character PDB identifier.

    chain:
        The chain identifier.
    """

    def __init__(self, name, chain=None):

        self.name = name.upper()
        self.chain = chain

        # made manual to completely control order
        ids = {
            'chain': chain,
            }
        self.identifiers = {}

        for name, identifier in ids.items():
            if identifier:
                self.identifiers[name] = identifier

    def __repr__(self):

        iditems = self.identifiers.items()

        kwargs = ', '.join(f'{key}={val!r}' for key, val in iditems)

        if kwargs:
            kwargs = ', ' + kwargs

        return '{}(name={!r}{})'.format(
            self.__class__.__name__,
            self.name,
            kwargs,
            )

    def __lt__(self, other):
        return str(self) < str(other)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return str(self) == str(other)

    def __str__(self):
        name = f'{self.name}'
        ids = '_'.join(self.identifiers.values())

        if ids:
            return f'{name}_' + ids
        else:
            return name



