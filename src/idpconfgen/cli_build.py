"""
Builds.

USAGE:
    $ idpconfgen build DB

"""
import argparse
import re
import random
from functools import partial
from itertools import cycle
from math import pi

import numpy as np

from idpconfgen import log
from idpconfgen.libs import libcli
from idpconfgen.libs.libcalc import make_coord_Q
from idpconfgen.libs.libio import read_dictionary_from_disk
from idpconfgen.libs.libfilter import (
    aligndb,
    regex_search,
    )
from idpconfgen.libs.libtimer import timeme
from idpconfgen.core.definitions import (
    distance_N_CA,
    distance_CA_C,
    distance_C_Np1,
    average_N_CA_C,
    average_CA_C_Np1,
    average_Cm1_N_CA,
    average_CA_C_O,
    average_Np1_C_O,
    atom_labels,
    aa1to3,
    )
from idpconfgen.core.exceptions import IDPConfGenException
from idpconfgen.libs.libpdb import atom_line_formatter, format_atom_name


_name = 'build'
_help = 'Builds conformers from database.'


_prog, _des, _us = libcli.parse_doc_params(__doc__)

ap = libcli.CustomParser(
    prog=_prog,
    description=libcli.detailed.format(_des),
    usage=_us,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    )
# https://stackoverflow.com/questions/24180527

ap.add_argument(
    '-db',
    '--database',
    help='The IDPConfGen database.',
    required=True,
    )

ap.add_argument(
    '-seq',
    '--input_seq',
    help='The Conformer residue sequence.',
    required=True
    )

ap.add_argument(
    '-n',
    '--nconfs',
    help='Number of conformers to build',
    default=1,
    )

ap.add_argument(
    '-dr',
    '--dssp-regexes',
    help='Regexes used to search in DSSP',
    default='(?=(L{2,6}))',
    nargs='+',
    )



def main(
        input_seq,
        database,
        func=None,
        dssp_regexes=r'(?=(L{2,6}))',
        nconfs=1,
        ):
    """."""
    db = read_dictionary_from_disk(database)
    ldb = len(db)
    log.info(f'Read DB with {ldb} entries')

    # reads and aligns IDPConfGen data base
    timed = partial(timeme, aligndb)
    pdbs, angles, dssp, resseq = timed(db)

    # seachs for slices in secondary structure
    timed = partial(timeme, regex_search)
    slices = []
    if isinstance(dssp_regexes, str):
        dssp_regexes = [dssp_regexes]

    for dssp_regex_string in dssp_regexes:
        slices.extend(timed(dssp, dssp_regex_string))

    log.info(f'Found {len(slices)} indexes for {dssp_regexes}')


    # building

    # prepares data based on the input sequence
    #len_conf = len(input_seq)  # number of residues
    atom_labels = np.array(generate_atom_labels(input_seq))  # considers sidechain all-atoms
    num_atoms = len(atom_labels)
    residue_numbers = np.array(generate_residue_numbers(atom_labels))
    coords = np.zeros((num_atoms, 3), dtype=np.float32)

    # creates masks
    bb_mask = np.isin(atom_labels, ('N', 'CA', 'C'))
    carbonyl_mask = np.isin(atom_labels, ('O',))

    # creates views
    bb = np.zeros((np.sum(bb_mask), 3), dtype=np.float64)
    bb_o = np.zeros((np.sum(carbonyl_mask), 3), dtype=np.float64)

    # places seed coordinates
    # coordinates are created always from the parameters in the core
    # definitions of IDPConfGen

    # first atom (N-terminal) is at 0, 0, 0 - no need to add it because
    # coords was created with np.zeros :-)

    # second atom (CA of the firs residue) is at the x-axis
    bb[1, :] = (distance_N_CA, 0.0, 0.0)

    # third atom (C of the first residue) needs to be computed according
    # to the bond length parameters and bend angle.
    bb[2, :] = make_coord_Q(
        np.array((0.0, distance_N_CA, 0.0)),  # dummy coordinate used only here
        bb[0, :],
        bb[1, :],
        distance_CA_C,
        pi - average_N_CA_C,
        0,  # null torsion angle
        )

    # prepares cycles for building process
    bond_lens = cycle([distance_C_Np1, distance_N_CA, distance_CA_C])
    bond_bend = cycle([pi - average_CA_C_Np1, pi - average_Cm1_N_CA, pi - average_N_CA_C])

    RC = random.choice
    i = 3  # starts at 2 because the first 3 atoms are already placed
    # and needs to adjust with the += assignment inside the loop
    last_O = 0  # carbonyl atoms
    while True:
        #agls = angles[RC(loops_6), :].ravel()[1:-2]
        agls = angles[RC(slices), :].ravel()[1:-2]
        i0 = i
        try:
            for torsion in agls:
                bb[i, :] = make_coord_Q(
                    bb[i - 3, :],
                    bb[i - 2, :],
                    bb[i - 1, :],
                    next(bond_lens),
                    next(bond_bend),
                    torsion,

                    )
                i += 1

            #else:
            #    # when backbone completes,
            #    # adds carbonyl oxygen atoms
            #    for k in range(i0, i, 3):
            #        bb_o[last_O, :] = make_coord_Q(
            #            bb[k - 2, :],
            #            bb[k - 1, :],
            #            bb[k, :],
            #            distance_N_CA,  # to change
            #            average_CA_C_O,
            #            0,
            #            )
            #        last_O += 1
        except IndexError:
            # i-1, to discard the last carboxyl
            #for k in range(i0, i-1, 3):
            #    bb_o[last_O, :] = make_coord_Q(
            #        bb[k - 2, :],
            #        bb[k - 1, :],
            #        bb[k, :],
            #        distance_N_CA,  # to change
            #        #average_CA_C_O,
            #        average_Np1_C_O,
            #        0,
            #        )
            #    last_O += 1
            break


# TODO:
# clashes
# sidechains
# carboxylo final
# correct distance C_O
# correct bend angle CA_C_O

    coords[bb_mask] = bb
    coords[carbonyl_mask] = bb_o

    relevant = bb_mask #np.isin(atom_labels, ('N', 'CA', 'C', 'O'))

    save_conformer_to_disk(
        input_seq,
        atom_labels[relevant],
        residue_numbers[relevant],
        coords[relevant],
        )


def save_conformer_to_disk(input_seq, atom_labels, residues, coords):
    lines = []
    LA = lines.append
    resi = -1
    for i in range(len(atom_labels)):
        if atom_labels[i] == 'N':
            resi += 1
        ele = atom_labels[i].lstrip('123')[0]
        LA(atom_line_formatter.format(
            'ATOM',
            i,
            format_atom_name(atom_labels[i], ele),
            '',
            aa1to3[input_seq[resi]],
            'A',
            residues[i],
            '',
            np.round(coords[i, 0], decimals=3),
            np.round(coords[i, 1], decimals=3),
            np.round(coords[i, 2], decimals=3),
            0.0,
            0.0,
            '',
            ele,
            '',
            )
        )

    with open('conformer.pdb', 'w') as fout:
        fout.write('\n'.join(lines))


def generate_atom_labels(input_seq, AL=atom_labels):
    """."""
    labels = []

    LE = labels.extend
    for residue in input_seq:
        LE(AL[residue])

    return labels


def generate_residue_numbers(atom_labels, start=1):
    """
    Create a list of residue numbers based on atom labels.

    Considers `N` to be the first atom of the residue.
    If this is not the case, the output can be meaningless.
    """
    if atom_labels[0] == 'N':
        start -= 1  # to compensate the +=1 implementation in the for loop

    residues = []
    RA = residues.append

    for al in atom_labels:
        if al == 'N':
            start += 1
        RA(start)

    return residues



if __name__ == "__main__":
    libcli.maincli(ap, main)
