"""
Defines small_a and small_h, conversion to Gauss and eV,
and the PaicosQuantity and PaicosTimeSeries classes.
"""
from fractions import Fraction
import numpy as np
import astropy.units as u
from astropy.units import Quantity
from astropy.units import UnitConversionError

_ns = globals()

small_a = u.def_unit(
    ["small_a"],
    prefixes=False,
    namespace=_ns,
    doc="Cosmological scale factor.",
    format={"latex": "a", "unicode": r"a"},
)
u.def_physical_type(small_a, "scale factor")


small_h = u.def_unit(
    ["small_h"],
    namespace=_ns,
    prefixes=False,
    doc='Reduced/"dimensionless" Hubble constant',
    format={"latex": r"h", "unicode": r"h"},
)

u.add_enabled_units(small_a)
u.add_enabled_units(small_h)

# Allows conversion between K and eV
u.add_enabled_equivalencies(u.temperature_energy())
# Allows conversion to Gauss (potential issues?)
# https://github.com/astropy/astropy/issues/7396

# The equivalencies sometimes frustratingly fail.
# TODO: Override the .to method ignore the Gauss component of the unit...
gauss_B = (u.g / u.cm)**(0.5) / u.s
equiv_B = [(u.G, gauss_B, lambda x: x, lambda x: x)]
Bscaling = small_a**(-2) * small_h
equiv_B_comoving = [(u.G * Bscaling, gauss_B * Bscaling, lambda x: x, lambda x: x)]
Bscaling = small_a**(-2)
equiv_B_no_small_h = [(u.G * Bscaling, gauss_B * Bscaling, lambda x: x, lambda x: x)]
u.add_enabled_equivalencies(equiv_B)
u.add_enabled_equivalencies(equiv_B_comoving)
u.add_enabled_equivalencies(equiv_B_no_small_h)


def get_unit_dictionaries(unit):
    """
    Returns dictionaries with information about the units of the
    quantity.
    """
    codic = {}
    dic = {}
    for base, power in zip(unit.bases, unit.powers):
        if base in (small_a, small_h):
            codic[base] = power
        else:
            dic[base] = power
    for key in [small_h, small_a]:
        if key not in codic:
            codic[key] = 0

    return codic, dic


def construct_unit_from_dic(dic):
    """
    Construct unit from a dictionary with the format returned
    from __get_unit_dictionaries
    """
    return np.prod([unit**dic[unit] for unit in dic])


def separate_units(unit):
    """
    Separate the standard physical units (u_unit) from the units involving
    a and h (pu_unit). That is,

    u_unit, pu_unit = separate_units(unit)

    where pu_unit contains small_a and small_h and u_unit contains
    everything else such that unit = u_unit * pu_unit
    """
    codic, dic = get_unit_dictionaries(unit)
    u_unit = construct_unit_from_dic(dic)
    pu_unit = construct_unit_from_dic(codic)
    return u_unit, pu_unit


def get_new_unit(unit, remove_list=[]):
    """
    Return new unit where base units in the remove list have been removed.
    """
    unit_list = []
    for base, power in zip(unit.bases, unit.powers):
        if base not in remove_list:
            unit_list.append(base**power)

    return np.prod(unit_list)


class PaicosQuantity(Quantity):

    """
    PaicosQuantity is a subclass of the astropy Quantity class which
    represents a number with some associated unit.

    This subclass in addition includes a and h factors used in the definition
    of comoving variables.

    Parameters
    ----------

    value: the numeric values of your data (similar to astropy Quantity)

    a: the cosmological scale factor of your data

    h: the reduced Hubble parameter, e.g. h = 0.7

    unit: a string, e.g. 'g/cm^3 small_a^-3 small_h^2' or astropy Unit
    The latter can be defined like this:

    from paicos import units as pu
    from astropy import units as u
    unit = u.g*u.cm**(-3)*small_a**(-3)*small_h**(2)

    The naming of small_a and small_h is to avoid conflict with the already
    existing 'annum' (i.e. a year) and 'h' (hour) units.

    Returns
    ----------

    Methods/properties
    ----------

    no_small_h: returns a new comoving quantity where the h-factors have
               been removed and the numeric value adjusted accordingly.

    to_physical: returns a new  object where both a and h factors have been
                 removed, i.e. we have switched from comoving values to
                 the physical value.

    label: Return a Latex label for use in plots.

    Examples
    ----------

    units = 'g cm^-3 small_a^-3 small_h^2'
    A = PaicosQuantity(2, units, h=0.7, a=1/128)

    # Create a new comoving quantity where the h-factors have been removed
    B = A.no_small_h

    # Create a new quantity where both a and h factor have been removed,
    # i.e. we have switched from a comoving quantity to the physical value

    C = A.to_physical

    """

    # pylint: disable=too-many-arguments

    def __new__(cls, value, unit=None, dtype=None, copy=False, order=None,
                subok=False, ndmin=0, h=None, a=None, comoving_sim=None):
        """
        Here we initialize the Paicos Quantity. The three additional
        input arguments (compared to a standard astropy quantity) are

        h
        a
        comoving_sim
        """

        assert h is not None, 'Paicos quantity is missing a value for h'
        assert a is not None, 'Paicos quantity is missing a value for a'
        assert comoving_sim is not None, 'is this from a comoving_sim?'

        if hasattr(value, 'unit'):
            unit = value.unit
            value = value.value

        obj = super().__new__(cls, value, unit=unit, dtype=dtype, copy=copy,
                              order=order, subok=subok, ndmin=ndmin)

        obj._h = h
        obj._a = a
        obj._comoving_sim = comoving_sim

        return obj

    def __array_finalize__(self, obj):
        """
        Heavily inspired by the astropy Quantity version
        """
        super_array_finalize = super().__array_finalize__
        if super_array_finalize is not None:
            super_array_finalize(obj)

        # If we're a new object or viewing an ndarray, nothing has to be done.
        if obj is None or obj.__class__ is np.ndarray:
            return

        # Set Paicos specific parameters
        self._h = getattr(obj, '_h', None)
        self._a = getattr(obj, '_a', None)
        self._comoving_sim = getattr(obj, '_comoving_sim', None)

    @property
    def a(self):
        """
        The scale factor.
        """
        if self.comoving_sim:
            return self._a
        raise RuntimeError('Non-comoving object has no scale factor')

    @property
    def h(self):
        """
        The reduced Hubble parameter
        """
        return self._h

    @property
    def comoving_sim(self):
        """
        Whether the simulation had ComovingIntegrationOn
        """
        return self._comoving_sim

    @property
    def z(self):
        """
        The redshift.
        """
        if self.comoving_sim:
            return 1. / self._a - 1.
        raise RuntimeError('Non-comoving object has no redshift')

    def lookback_time(self, reader_object):
        """
        The lookback time.

        Requires a reader object as input (e.g. a snap,
        cat or other instance of Snapshot, Catalog or PaicosReader)
        """
        if self.comoving_sim:
            return reader_object.get_lookback_time(self.z)
        msg = 'lookback_time not defined for non-comoving sim'
        raise RuntimeError(msg)

    def age(self, reader_object):
        """
        The age of the universe in the simulation.

        Requires a reader object as input (e.g. a snap,
        cat or other instance of Snapshot, Catalog or PaicosReader)
        """
        if self.comoving_sim:
            return reader_object.get_age(self.z)
        msg = 'age not defined for non-comoving sim'
        raise RuntimeError(msg)

    @property
    def time(self):
        """
        The time elapsed since the beginning of the simulation.

        Only defined for non-comoving simulations.
        """
        if self.comoving_sim:
            msg = 'time not defined for comoving sim'
            raise RuntimeError(msg)

        if hasattr(self._a, 'unit'):
            return self._a
        else:
            return self._a * u.Unit('arepo_time')

    @property
    def unit_quantity(self):
        """
        Returns a new PaicosQuantity with the same units as the current
        PaicosQuantity and a numeric value of 1.
        """
        return PaicosQuantity(1., self.unit, a=self._a, h=self.h,
                              comoving_sim=self.comoving_sim)

    @property
    def copy(self):
        """
        Returns a copy of the PaicosQuantity
        """
        return PaicosQuantity(np.array(self.value), self.unit, a=self._a, h=self.h,
                              comoving_sim=self.comoving_sim, copy=True)

    @property
    def uq(self):
        """
        A short hand for the 'unit_quantity' method.
        """
        return self.unit_quantity

    @property
    def hdf5_attrs(self):
        """
        Give the units as a dictionary for hdf5 data set attributes
        """
        return {'unit': self.unit.to_string()}

    @property
    def no_small_h(self):
        """
        Remove scaling with h, returning a quantity with adjusted values.
        """
        codic, _ = get_unit_dictionaries(self.unit)
        factor = self.h**codic[small_h]

        value = self.view(np.ndarray)
        new_unit = get_new_unit(self.unit, [small_h])
        return self._new_view(value * factor, new_unit)

    @property
    def cgs(self):
        """
        Returns a copy of the current `PaicosQuantity` instance with CGS units.
        The value of the resulting object will be scaled.
        """
        u_unit, pu_unit = separate_units(self.unit)
        cgs_unit = u_unit.cgs
        new_unit = pu_unit * cgs_unit / cgs_unit.scale
        return self._new_view(self.value * cgs_unit.scale, new_unit)

    @property
    def si(self):
        """
        Returns a copy of the current `PaicosQuantity` instance with SI units.
        The value of the resulting object will be scaled.
        """
        u_unit, pu_unit = separate_units(self.unit)
        si_unit = u_unit.si
        new_unit = pu_unit * si_unit / si_unit.scale
        return self._new_view(self.value * si_unit.scale, new_unit)

    def to(self, unit, equivalencies=[], copy=True):
        """
        Convert to different units. Similar functionality to the astropy
        Quantity.to() method.
        """
        if isinstance(unit, str):
            unit = u.Unit(unit)

        u_unit, pu_unit = separate_units(self.unit)

        u_unit_to, pu_unit_to = separate_units(unit)

        if pu_unit_to == u.Unit(''):
            return super().to(unit * pu_unit, equivalencies, copy)
        elif pu_unit == pu_unit_to:
            return super().to(unit, equivalencies, copy)
        else:
            err_msg = ('\n\nYou have requested conversion from\n {} '
                       + '\nto\n {} . \nThis is not possible as the a and h '
                       + 'factors differ. I.e. you cannot convert from\n '
                       + '{}\nto\n {}\nUse the .to_physical or .no_small_h '
                       + 'methods if you are trying to get rid of the a '
                       + 'and h factors.')

            raise RuntimeError(err_msg.format(self.unit, unit, pu_unit, pu_unit_to))

    @property
    def arepo(self):
        """
        Returns the quantity in Arepo code units.
        """
        arepo_bases = set([u.Unit('arepo_mass'),
                           u.Unit('arepo_length'),
                           u.Unit('arepo_time')])
        try:
            return self.decompose(bases=arepo_bases)
        except UnitConversionError as inst:
            err_msg = ('Conversion to arepo_units does not work well for '
                       + 'Temperature and magnetic field strength in Gauss. '
                       + 'Astropy throws the following error: ' + str(inst))

            raise UnitConversionError(err_msg) from inst

        return None

    @property
    def astro(self):
        """
        Returns the quantity in typical units used in cosmological simulations
        """
        return self.decompose(bases=[u.kpc, u.Msun, u.s, u.uG, u.keV, u.K])

    def decompose(self, bases=[]):
        """
        Decompose into a different set of units, e.g.

        A = B.decompose(bases=[u.kpc, u.Msun, u.s, u.uG, u.keV])

        small_a and small_h are automatically included in the bases.
        """
        _, pu_unit = separate_units(self.unit)
        if len(bases) == 0 or pu_unit == u.Unit(''):
            return super().decompose(bases)

        if isinstance(bases, set):
            bases = list(bases)
        bases.append(small_a)
        bases.append(small_h)
        bases = set(bases)
        return super().decompose(bases)

    def label(self, variable=''):
        """
        Return a Latex string for use in plots. The optional
        input variable could be the Latex symbol for the physical variable,
        for instance \rho or \nabla\times\vec{v}.
        """

        a_sc, a_sc_str = self.__scaling_and_scaling_str(small_a)
        h_sc, h_sc_str = self.__scaling_and_scaling_str(small_h)

        co_label = a_sc_str + h_sc_str

        normal_unit = get_new_unit(self.unit, [small_h, small_a])

        _, dic = get_unit_dictionaries(self.unit)

        unit_label = ''
        for ii, key in enumerate(dic.keys()):
            _, unit_str = self.__scaling_and_scaling_str(key)
            unit_label += unit_str
            if ii < len(dic.keys()) - 1:
                unit_label += r'\;'

        label = co_label + r'\; \left[' + unit_label + r'\right]'

        # Get ckpc, cMpc, ckpc/h and Mkpc/h as used in literature
        if normal_unit in ('kpc', 'Mpc', 'Gpc'):
            if a_sc in (0, 1):
                if h_sc in (0, -1):
                    if a_sc == 1:
                        label = r'\mathrm{c}' + unit_label
                    elif a_sc == 0:
                        label = unit_label
                    if h_sc == -1:
                        label = label + r'\;h^{-1}'

            label = '[' + label + ']'

        if len(variable) > 0:
            label = variable + r'\;' + label
        label = '$' + label + '$'

        return label

    @property
    def to_physical(self):
        """
        Returns a copy of the current `PaicosQuantity` instance with the
        a and h factors removed, i.e. transform from comoving to physical.
        The value of the resulting object is scaled accordingly.
        """
        codic, _ = get_unit_dictionaries(self.unit)
        factor = self.h**codic[small_h]

        if self.comoving_sim:
            factor *= self.a**codic[small_a]

        value = self.view(np.ndarray)
        new_unit = get_new_unit(self.unit, [small_a, small_h])
        return self._new_view(value * factor, new_unit)

    def to_comoving(self, unit):
        """
        Returns a copy of the current `PaicosQuantity` instance with the
        a and h factors given by the input unit.
        """

        if not self.comoving_sim:
            raise RuntimeError('Only implemented for comoving simulations')

        if isinstance(unit, str):
            unit = u.Unit(unit)

        u_unit_to, pu_unit_to = separate_units(unit)

        u_unit, pu_unit = separate_units(self.unit)

        if u_unit_to == u.Unit(''):
            u_unit_to = u_unit
        elif u_unit_to != u_unit:
            raise RuntimeError('This method can only change the a and h factors!')

        change_pu = pu_unit / pu_unit_to

        codic, _ = get_unit_dictionaries(change_pu)
        factor = self.h**codic[small_h]

        if self.comoving_sim:
            factor *= self.a**codic[small_a]

        value = self.view(np.ndarray)
        new_unit = self.unit / change_pu

        return self._new_view(value * factor, new_unit)

    def __scaling_and_scaling_str(self, unit):
        """
        Helper function to create labels
        """
        codic, dic = get_unit_dictionaries(self.unit)
        # print(unit, dic, codic)
        if unit in codic:
            scaling = codic[unit]
        elif unit in dic:
            scaling = dic[unit]
        else:
            raise RuntimeError('should not happen')

        if unit in codic:
            base_string = unit.to_string(format='unicode')
        elif unit in dic:
            base_string = unit.to_string(format='latex')[1:-1]
        scaling_str = str(Fraction(scaling).limit_denominator(10000))
        if scaling_str == '0':
            scaling_str = ''
        elif scaling_str == '1':
            scaling_str = base_string
        else:
            scaling_str = base_string + '^{' + scaling_str + '}'
        return scaling, scaling_str

    def _sanity_check(self, value):
        """
        Function for sanity-checking addition, subtraction, multiplication
        and division of quantities. They should all have same a and h.
        """
        # pylint: disable=protected-access
        err_msg = "Operation requires objects to have same a and h value."
        if isinstance(value, PaicosQuantity):
            if value._a != self._a:
                info = f' Obj1._a={self._a}, Obj2._a={value._a}'
                raise RuntimeError(err_msg + info)
            if value.h != self.h:
                info = f' Obj1.h={self.h}, Obj2.h={value.h}'
                raise RuntimeError(err_msg + info)

    def _repr_latex_(self):
        number_part = super()._repr_latex_().split('\\;')[0]
        _, pu_units = separate_units(self.unit)
        u_latex = (self.unit / pu_units).to_string(format='latex')[1:-1]
        pu_latex = pu_units.to_string(format='latex')[1:-1]

        if pu_units != u.Unit(''):
            modified = number_part + '\\;' + u_latex + \
                '\\times' + pu_latex + '$'
        else:
            modified = number_part + '\\;' + u_latex + '$'
        return modified

    def __add__(self, value):
        self._sanity_check(value)
        return super().__add__(value)

    def __sub__(self, value):
        self._sanity_check(value)
        return super().__sub__(value)

    def __mul__(self, value):
        self._sanity_check(value)
        return super().__mul__(value)

    def __truediv__(self, value):
        self._sanity_check(value)
        return super().__truediv__(value)

    def dump(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")

    def dumps(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")

    def tobytes(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")

    def tofile(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")

    def tolist(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")

    def tostring(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")

    def choose(self):
        """This astropy Quantity method has not been implemented the Paicos subclasses."""
        raise RuntimeError("not implemented")


class PaicosTimeSeries(PaicosQuantity):

    """
    PaicosTimeSeries is a subclass of the PaicosQuantity and and shares many
    of the same methods.

    The time series is very similar to the PaicosQuantity but
    the .a or .time properties now return arrays with same length
    as the object itself (.shape[0]).
    """

    def __new__(cls, value, unit=None, dtype=None, copy=True, order=None,
                subok=False, ndmin=0, h=None, a=None, comoving_sim=None):

        if isinstance(value, list):
            h = value[0].h  # Could check that they are all the same...
            comoving_sim = value[0].comoving_sim
            unit = value[0].unit
            dtype = value[0].dtype
            a = np.array([value[i]._a for i in range(len(value))])
            value = np.array([value[i].value for i in range(len(value))])
        elif isinstance(value, np.ndarray):
            assert h is not None
            assert a is not None
            assert isinstance(a, np.ndarray)
            assert a.shape[0] == value.shape[0]
            if hasattr(value, 'unit'):
                if unit is not None:
                    raise RuntimeError(
                        'value has units but you are also passing unit={}:'.format(unit))
                unit = value.unit
                value = value.value
        else:
            raise RuntimeError('unexpected input for value:', value)

        msg = ('PaicosTimeSeries requires that the length of the first '
               + 'dimension is equal to the length of the time array')
        assert value.shape[0] == a.shape[0], msg

        assert len(value.shape) <= 3, 'Only 1D, 2D and 3D arrays are supported'

        obj = super().__new__(cls, value, unit=unit, dtype=dtype, copy=copy,
                              order=order, subok=subok, ndmin=ndmin, h=h, a=a,
                              comoving_sim=comoving_sim)

        obj._h = h
        obj._a = a
        obj._comoving_sim = comoving_sim

        return obj

    @property
    def to_physical(self):
        """
        Returns a copy of the current `PaicosTimeSeries` instance with the
        a and h factors removed, i.e. transform from comoving to physical.
        The value of the resulting object is scaled accordingly.
        """
        codic, _ = get_unit_dictionaries(self.unit)
        factor = self.h**codic[small_h]

        if self.comoving_sim:
            factor *= self.a**codic[small_a]

        value = self.view(np.ndarray)
        new_unit = get_new_unit(self.unit, [small_a, small_h])

        if len(value.shape) == 1:
            new_value = value * factor
        elif len(value.shape) == 2:
            new_value = value * factor[:, None]
        elif len(value.shape) == 3:
            new_value = value * factor[:, None, None]

        return self._new_view(new_value, new_unit)

    def to_comoving(self, unit):
        """
        Returns a copy of the current `PaicosTimeSeries` with the
        a and h factors given by the input unit.
        """

        if not self.comoving_sim:
            raise RuntimeError('Only implemented for comoving simulations')

        if isinstance(unit, str):
            unit = u.Unit(unit)

        u_unit_to, pu_unit_to = separate_units(unit)
        u_unit, pu_unit = separate_units(self.unit)

        if u_unit_to == u.Unit(''):
            u_unit_to = u_unit
        elif u_unit_to != u_unit:
            raise RuntimeError('This method can only change the a and h factors!')

        change_pu = pu_unit / pu_unit_to

        codic, _ = get_unit_dictionaries(change_pu)
        factor = self.h**codic[small_h]

        if self.comoving_sim:
            factor *= self.a**codic[small_a]

        value = self.view(np.ndarray)
        new_unit = self.unit / change_pu

        if len(value.shape) == 1:
            new_value = value * factor
        elif len(value.shape) == 2:
            new_value = value * factor[:, None]
        elif len(value.shape) == 3:
            new_value = value * factor[:, None, None]

        return self._new_view(new_value, new_unit)

    @property
    def hdf5_attrs(self):
        """
        Give the units as a dictionary for hdf5 data set attributes
        """
        return {'unit': self.unit.to_string(), 'Paicos': 'PaicosTimeSeries'}

    @property
    def copy(self):
        """
        Returns a copy of the PaicosQuantity
        """
        return PaicosTimeSeries(self.value, self.unit, a=self._a, h=self.h,
                                copy=True, comoving_sim=self.comoving_sim)

    def make_matrix(self, vec):
        """
        """
        assert vec.shape[0] == self.shape[0]
        return np.vstack([vec for _ in range(self.shape[1])]).T

    def _sanity_check(self, value):
        """
        Function for sanity-checking addition, subtraction, multiplication
        and division of quantities. They should all have same a and h.
        """
        err_msg = "Operation requires objects to have same a and h value.\n"
        if isinstance(value, PaicosQuantity):
            if not isinstance(value, PaicosTimeSeries):
                msg = ('operations combining PaicosQuantity and '
                       + 'PaicosTimeSeries is not allowed.')
                raise RuntimeError(msg)

        if isinstance(value, PaicosTimeSeries):
            info = f'\nObj1.a={self._a}.\n\nObj2.a={value._a}'
            try:
                np.testing.assert_array_equal(value._a, self._a)
            except AssertionError as exc:
                raise RuntimeError(err_msg + info) from exc
            if value.h != self.h:
                info = f'\nObj1.h={self.h}.\n\nObj2.h={value.h}'
                raise RuntimeError(err_msg + info)
