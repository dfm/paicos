import numpy as np


def get_variable_function_gas(variable_str, info=False):

    def GFM_MetallicityTimesMasses(snap):
        return snap['0_Masses']*snap['0_GFM_Metallicity']

    def Volumes(snap):
        return snap["0_Masses"] / snap["0_Density"]

    def EnergyDissipation(snap):
        return snap['0_EnergyDissipation']

    def MachnumberTimesEnergyDissipation(snap):
        variable = snap['0_Machnumber']*snap['0_EnergyDissipation']
        return variable

    def MagneticFieldSquared(snap):
        return np.sum(snap['0_MagneticField']**2, axis=1)

    def MagneticFieldStrength(snap):
        return np.sqrt(np.sum(snap['0_MagneticField']**2, axis=1))

    def VelocityMagnitude(snap):
        return np.sqrt(np.sum(snap['0_Velocities']**2, axis=1))

    def MagneticFieldSquaredTimesVolumes(snap):
        variable = snap["0_Volumes"]*np.sum(snap['0_MagneticField']**2, axis=1)
        return variable

    def Pressure(snap):
        if snap.gamma == 1:
            msg = 'Temperature field not supported for isothermal EOS!'
            raise RuntimeError(msg)
        gm1 = snap.gamma - 1
        variable = snap["0_InternalEnergy"] * snap["0_Density"] * gm1
        return variable

    def PressureTimesVolumes(snap):
        if '0_Pressure' in snap.keys():
            return snap['0_Pressure'] * snap['0_Volumes']
        else:
            if snap.gamma != 1:
                gm1 = snap.gamma - 1
                variable = snap["0_Masses"] * snap["0_InternalEnergy"] * gm1
            else:
                variable = snap['0_Volumes'] * snap['0_Pressure']

        return variable

    def Temperatures(snap):
        from astropy import constants as c
        mhydrogen = c.m_e + c.m_p

        gm1 = snap.gamma - 1

        if snap.gamma == 1:
            msg = 'Temperature field not supported for isothermal EOS!'
            raise RuntimeError(msg)

        mmean = snap['0_MeanMolecularWeight']

        # temperature in Kelvin
        from . import settings
        if settings.use_units:
            variable = (gm1 * snap["0_InternalEnergy"] *
                        mmean * mhydrogen).to('K')
        else:
            u_v = snap.converter.arepo_units['unit_velocity']
            variable = (gm1 * snap["0_InternalEnergy"] *
                        u_v**2 * mmean * mhydrogen
                        ).to('K').value
        return variable

    def TemperaturesTimesMasses(snap):
        return snap["0_Temperatures"]*snap['0_Masses']

    def Current(snap):

        def get_index(ii, jj):
            return ii*3 + jj
        gradB = snap['0_BfieldGradient']
        J_x = gradB[:, get_index(2, 1)] - gradB[:, get_index(1, 2)]
        J_y = gradB[:, get_index(0, 2)] - gradB[:, get_index(2, 0)]
        J_z = gradB[:, get_index(1, 0)] - gradB[:, get_index(0, 1)]

        J = np.sqrt(J_x**2 + J_y**2 + J_z**2)
        return J

    def Enstrophy(snap):
        # absolute vorticity squared times one half ("enstrophy")

        def get_index(ii, jj):
            return ii*3 + jj
        gradV = snap['0_VelocityGradient'][()]
        vor_x = gradV[:, get_index(2, 1)] - gradV[:, get_index(1, 2)]
        vor_y = gradV[:, get_index(0, 2)] - gradV[:, get_index(2, 0)]
        vor_z = gradV[:, get_index(1, 0)] - gradV[:, get_index(0, 1)]

        enstrophy = 0.5 * (vor_x**2 + vor_y**2 + vor_z**2)
        return enstrophy

    def EnstrophyTimesMasses(snap):
        # absolute vorticity squared times one half ("enstrophy")

        # Reshaping is slow
        if False:
            n_cells = snap['0_VelocityGradient'].shape[0]

            # Reshape to tensor form
            gradV = snap['0_VelocityGradient'].reshape(n_cells, 3, 3)
            # Get vorticity components
            vor_x = gradV[:, 2, 1] - gradV[:, 1, 2]
            vor_y = gradV[:, 0, 2] - gradV[:, 2, 0]
            vor_z = gradV[:, 1, 0] - gradV[:, 0, 1]
        else:
            def get_index(ii, jj):
                return ii*3 + jj
            gradV = snap['0_VelocityGradient']
            vor_x = gradV[:, get_index(2, 1)] - gradV[:, get_index(1, 2)]
            vor_y = gradV[:, get_index(0, 2)] - gradV[:, get_index(2, 0)]
            vor_z = gradV[:, get_index(1, 0)] - gradV[:, get_index(0, 1)]
        # The vorticity vector
        # vorticity = np.stack([vor_x, vor_y, vor_z], axis=1)

        enstrophy = 0.5 * (vor_x**2 + vor_y**2 + vor_z**2)
        variable = enstrophy*snap['0_Masses']

        return variable

    def MeanMolecularWeight(snap):
        if 'GFM_Metals' in snap.info(0, False):
            hydrogen_abundance = snap['0_GFM_Metals'][:, 0]
        else:
            hydrogen_abundance = 0.76

        if 'ElectronAbundance' in snap.info(0, False):
            electron_abundance = snap['0_ElectronAbundance']
            # partially ionized
            mean_molecular_weight = 4. / (1. + 3. * hydrogen_abundance +
                                          4. * hydrogen_abundance *
                                          electron_abundance)
        else:
            # fully ionized
            mean_molecular_weight = 4. / (5. * hydrogen_abundance + 3.)
        return mean_molecular_weight

    def NumberDensity(snap):
        """
        The gas number density in cm⁻³.
        """
        from astropy import constants as c
        density = snap['0_Density'].cgs
        mean_molecular_weight = snap['0_MeanMolecularWeight']
        proton_mass = c.m_p.to('g')
        number_density_gas = density / (mean_molecular_weight * proton_mass)
        return number_density_gas

    def MagneticCurvature(snap):
        from . import util

        @util.remove_astro_units
        def get_func(B, gradB):
            from .cython.get_derived_variables import get_curvature
            return get_curvature(B, gradB)

        curva = get_func(snap['0_MagneticField'], snap['0_BfieldGradient'])
        unit_quantity = snap['0_BfieldGradient'].uq / snap['0_MagneticField'].uq
        curva = curva * unit_quantity
        return curva

    def VelocityCurvature(snap):
        from . import util

        @util.remove_astro_units
        def get_func(V, gradV):
            from .cython.get_derived_variables import get_curvature
            return get_curvature(V, gradV)

        curva = get_func(snap['0_Velocities'], snap['0_VelocityGradient'])
        unit_quantity = snap['0_VelocityGradient'].uq/snap['0_Velocities'].uq
        curva = curva * unit_quantity
        return curva

    functions = {
        "0_GFM_MetallicityTimesMasses": GFM_MetallicityTimesMasses,
        "0_Volumes": Volumes,
        "0_Temperatures": Temperatures,
        "0_EnergyDissipation": EnergyDissipation,
        "0_MachnumberTimesEnergyDissipation": MachnumberTimesEnergyDissipation,
        "0_MagneticFieldSquared": MagneticFieldSquared,
        "0_MagneticFieldStrength": MagneticFieldStrength,
        "0_MagneticFieldSquaredTimesVolumes": MagneticFieldSquaredTimesVolumes,
        "0_Pressure": Pressure,
        "0_PressureTimesVolumes": PressureTimesVolumes,
        "0_TemperaturesTimesMasses": TemperaturesTimesMasses,
        "0_Current": Current,
        "0_Enstrophy": Enstrophy,
        "0_EnstrophyTimesMasses": EnstrophyTimesMasses,
        "0_MeanMolecularWeight": MeanMolecularWeight,
        "0_NumberDensity": NumberDensity,
        "0_MagneticCurvature": MagneticCurvature,
        "0_VelocityMagnitude": VelocityMagnitude,
        "0_VelocityCurvature": VelocityCurvature
    }

    if info:
        return list(functions.keys())
    else:
        if variable_str in functions:
            return functions[variable_str]
        else:
            msg = ('\n\nA function to calculate the variable {} is not ' +
                   'implemented!\n\nThe currently implemented variables ' +
                   'are:\n\n{}')
            raise RuntimeError(msg.format(variable_str, functions.keys()))