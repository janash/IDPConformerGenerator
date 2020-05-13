"""Mathemical calculations."""
import math

import numpy as np

from idpconfgen import log
from idpconfgen.libs import libstructure

AXIS_111 = np.array([
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
    ])


def make_axis_vectors(A, B, C):
    """
    Make axis vectors.

    For np.array([x,y,z]) of connected atoms A->B->C.

    Example
    -------
        >>> av = np.array([0.000, 0.000, 0.000])
        >>> bv = np.array([1.458, 0.000, 0.000])
        >>> cv = np.array([2.009, 1.420, 0.000])
        >>> make_axis_vectors(av, bv, cv)
        >>> (array([ 0.,  0., -1.]),
        >>>  array([-1.,  0.,  0.]),
        >>>  array([-0., -1., -0.]))

    Parameters
    ----------
    A, B, C : np.array of shape (3,).
        3D coordinate points in space.

    Returns
    -------
    tuple
        Three vectors defining the of ABC plane.
    """
    AB_vect = np.subtract(A, B)

    # vector parallel to ABC plane
    parallel_ABC = np.cross(
        AB_vect,
        np.subtract(C, B),
        )

    # perpendicular to parallel
    perpendicular = np.cross(
        AB_vect,
        parallel_ABC,
        )

    Alen = np.linalg.norm(AB_vect)
    if Alen > 0.0:
        AB_vect /= Alen

    Nlen = np.linalg.norm(parallel_ABC)
    if Nlen > 0.0:
        parallel_ABC /= Nlen

    Clen = np.linalg.norm(perpendicular)
    if Clen > 0.0:
        perpendicular /= Clen

    return parallel_ABC, AB_vect, perpendicular


def rotation_to_plane(A, B, C):
    """
    Define rotations matricex for planar orientation.

    Where, A->B determine the X axis, Y is the normal vector to the ABC
        plane, and A is defined at 0,0,0.

    .. seealso::

        :func:`make_axis_vectors`

    Parameters
    ----------
    A, B, C: np.array of shape (3,)
        The 3D coordinates, where A is the parent coordinate,
        B is the Xaxis and C the Yaxis.

    Returns
    -------
    np.array of shape (3,3)
        Rotational matrix
    """
    parallel_ABC, AB_vect, perpendicular = make_axis_vectors(A, B, C)
    b = np.array([AB_vect, -perpendicular, parallel_ABC])

    v = AXIS_111

    return np.dot(b, v).T


def make_coord(theta, phi, distance, parent, xaxis, yaxis):
    """
    Make a new coordinate in space.

    .. seealso::

        :func:`make_coord_from_angles`, :func:`rotation_to_plane`.

    Parameters
    ----------
    theta : float
        The angle in radians between `parent` and `yaxis`.

    phi : float
        The torsion angles in radians between `parent-xaxis-yaxis`
        plane and new coordinate.

    distance : float
        The distance between `parent` and the new coordinate.

    parent : np.array of shape (3,)
        The coordinate in space of the parent atom (point). The parent
        atom is the one that preceeds the newly added coordinate.

    xaxis : np.array of shape (3,)
        The coordinate in space that defines the xaxis of the
        parent-xaxis-yaxis coordinates plane.

    yaxis : np.array of shape (3,)
        The coordinate in space that defines the yaxis of the
        parent-xaxis-yaxis coordinates plane.

    Returns
    -------
    np.array of shape (3,)
        The new coordinate in space.
    """
    new_coord = make_coord_from_angles(theta, phi, distance)
    rotation = rotation_to_plane(parent, xaxis, yaxis)
    new_coord = np.dot(new_coord, rotation.T)
    return new_coord + parent


def make_coord_from_angles(theta, phi, distance):
    """
    Make axis components from angles.

    Performs:
        np.array([
            distance * math.cos(phi),
            distance * math.sin(phi) * math.cos(theta),
            distance * math.sin(phi) * math.sin(theta),
            ])

    Returns
    -------
    np.array of shape (3,)
    """
    return np.array([
        distance * math.cos(phi),
        distance * math.sin(phi) * math.cos(theta),
        distance * math.sin(phi) * math.sin(theta),
        ])


def calc_torsion_angles(coords):
    """
    Calculates torsion angles from sequential coordinates.

    Uses ``NumPy`` to compute angles in a vectorized fashion.
    Sign of the torsion angle is also calculated.

    Uses Prof. Azevedo implementation:
    https://azevedolab.net/resources/dihedral_angle.pdf

    Example
    -------
    Given the sequential coords that represent a dummy molecule of
    four atoms:

    >>> xyz = numpy.array([
    >>>     [0.06360, -0.79573, 1.21644],
    >>>     [-0.47370, -0.10913, 0.77737],
    >>>     [-1.75288, -0.51877, 1.33236],
    >>>     [-2.29018, 0.16783, 0.89329],
    >>>     ])

    A1---A2
           \
            \
            A3---A4

    Calculates the torsion angle in A2-A3 that would place A4 in respect
    to the plane (A1, A2, A3).

    Likewise, for a chain of N atoms A1, ..., An, calculates the torsion
    angles in (A2, A3) to (An-2, An-1). (A1, A2) and (An-1, An) do not
    have torsion angles.

    If coords represent a protein backbone consisting of N, CA, and C
    atoms and starting at the N-terminal, the torsion angles are given
    by the following slices to the resulting array:

    - phi (N-CA), [2::3]
    - psi (CA-C), [::3]
    - omega (C-N), [1::3]

    Parameters
    ----------
    coords : numpy.ndarray of shape (N>=4, 3)
        Where `N` is the number of atoms, must be equal or above 4.

    Returns
    -------
    numpy.ndarray of shape (N - 3,)
        The torsion angles in radians.
        If you want to convert those to degrees just apply
        ``np.degrees`` to the returned result.
    """
    # requires
    assert coords.shape[0] > 3
    assert coords.shape[1] == 3

    # Yes, I always write explicit array indices! :-)
    q_vecs = coords[1:, :] - coords[:-1, :]
    cross = np.cross(q_vecs[:-1, :], q_vecs[1:, :])
    unitary = cross / np.linalg.norm(cross)

    # components
    # u0 comes handy to define because it fits u1
    u0 = unitary[:-1, :]

    # u1 is the unitary cross products of the second plane
    # that is the unitary q2xq3, obviously applied to the whole chain
    u1 = unitary[1:, :]

    # u3 is the unitary of the bonds that have a torsion representation,
    # those are all but the first and the last
    u3 = q_vecs[1:-1] / np.linalg.norm(q_vecs[1:-1])

    # u2
    # there is no need to further select dimensions for u2, those have
    # been already sliced in u1 and u3.
    u2 = np.cross(u3, u1)

    # calculating cos and sin of the torsion angle
    # here we need to use the .T and np.diagonal trick to achieve
    # broadcasting along the whole coords chain
    cos_theta = np.diagonal(np.dot(u0, u1.T))
    sin_theta = np.diagonal(np.dot(u0, u2.T))

    # torsion angles
    return -np.arctan2(sin_theta, cos_theta)


def validate_array_for_torsion(data):
    """Validates data for torsion angle calculation."""

    if data[0, libstructure.col_name] != 'N':
        return 'The first atom is not N, it should be!'

    if data.shape[0] % 3:
        return 'Number of backbone atoms is not module of 3.'

    return ''

