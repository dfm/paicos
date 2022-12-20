import h5py
import numpy as np
from paicos.util import save_dataset
import paicos as pa


class RadialProfiles:

    def __init__(self, radial_filename, arepo_snap, center, r_max, bins,
                 verbose=False):
        from paicos import Histogram
        if verbose:
            import time
            t = time.time()

        self.snap = arepo_snap

        self.center = np.array(center)

        self.verbose = verbose

        self.snap.load_data(0, 'Coordinates')
        pos = self.snap.P['0_Coordinates']

        r = np.sqrt(np.sum((pos-center[None, :])**2., axis=1))

        self.index = r < r_max*1.1

        self.h_r = Histogram(r[self.index], bins=bins, verbose=verbose)

        self.radial_filename = radial_filename
        tmp_list = radial_filename.split('/')
        tmp_list[-1] = 'tmp_' + tmp_list[-1]
        self.tmp_radial_filename = ''
        for ii in range(0, len(tmp_list)-1):
            self.tmp_radial_filename += tmp_list[ii] + '/'
        self.tmp_radial_filename += tmp_list[-1]

        self.create_tmp_radial_file()

        self.copy_over_snapshot_information()

        variable_strings = ['Masses', 'Volumes', 'TemperatureTimesMasses',
                            'MagneticFieldSquaredTimesVolumes',
                            'PressureTimesVolumes']
        for variable_str in variable_strings:
            self.add_profile(variable_str)

        if 'VelocityGradient' in self.snap.info(0, False):
            self.add_profile('EnstrophyTimesMasses')
        if 'GFM_Metallicity' in self.snap.info(0, False):
            self.add_profile('GFM_MetallicityTimesMasses')

        # Delete all gas variables for memory efficiency
        keys = list(self.snap.P.keys())
        for key in keys:
            if key[0] == '0':
                del self.snap.P[key]

        # Now do the dark matter

        for part in [1, 2, 3]:

            if self.verbose:
                print('Working on mass profile for DM type', part)
            # Load Dark matter positions
            if self.snap.info(part, False) is not None:
                self.snap.load_data(part, "Coordinates")

                pos = self.snap.P[str(part) + '_Coordinates']

                # Radius from center of cluster
                r = np.sqrt(np.sum((pos-center[None, :])**2., axis=1))

                # snap.load_data(part, "SubfindHsml")
                dm_mass = self.snap.Header["MassTable"][part]
                if pa.util.use_paicos_quantities:
                    dm_mass = self.snap.converter.get_paicos_quantity(dm_mass,
                                                                      'Masses')

                if part != 2:
                    masses = np.ones(self.snap.P[str(part) +
                                     '_Coordinates'].shape[0],
                                     dtype=np.float32) * dm_mass
                else:
                    self.snap.load_data(part, "Masses")
                    masses = self.snap.P['2_Masses']

                index = r < r_max*1.1
                masses = masses[index]
                r = r[index]
                hist, edges = np.histogram(r, bins=bins, weights=masses)
                with h5py.File(self.tmp_radial_filename, 'r+') as f:
                    save_dataset(f, 'DM_Masses_part' + str(part), data=hist)

        bin_volumes = np.diff(4/3*np.pi*bins**3)
        with h5py.File(self.tmp_radial_filename, 'r+') as f:
            save_dataset(f, 'bin_volumes', data=bin_volumes)

        # Move to final hdf5 file
        # self.finalize()

        if verbose:
            print('Radial profile took {:1.2f} seconds'.format(time.time()-t))

    def add_profile(self, variable_str):
        from paicos import get_variable

        if self.verbose:
            import time
            print('Working on profile for', variable_str)
            t = time.time()

        variable = get_variable(self.snap, variable_str)[self.index]

        with h5py.File(self.tmp_radial_filename, 'r+') as f:
            save_dataset(f, variable_str, self.h_r.hist(variable))

        if self.verbose:
            dur = time.time() - t
            print('which took {:1.2f} seconds'.format(dur))

    def finalize(self):
        """
        # TODO: Overload an out-of-scope operator instead?
        """
        import os
        os.rename(self.tmp_radial_filename, self.radial_filename)

    def create_tmp_radial_file(self):

        self.arepo_snap_filename = snap.first_snapfile_name

        with h5py.File(self.tmp_radial_filename, 'w') as f:
            save_dataset(f, 'bin_centers', self.h_r.bin_centers)
            save_dataset(f, 'bins', data=self.h_r.bins)
            save_dataset(f, 'center', data=self.center)

    def copy_over_snapshot_information(self):
        """
        Copy over attributes from the original arepo snapshot.
        In this way we will have access to units used, redshift etc
        """
        g = h5py.File(self.snap.first_snapfile_name, 'r')
        with h5py.File(self.tmp_radial_filename, 'r+') as f:
            for group in ['Header', 'Parameters', 'Config']:
                f.create_group(group)
                for key in g[group].attrs.keys():
                    f[group].attrs[key] = g[group].attrs[key]
        g.close()


if __name__ == '__main__':
    from paicos import Snapshot
    from paicos import root_dir

    pa.use_units(True)

    snap = Snapshot(root_dir + '/data', 247)
    center = snap.Cat.Group['GroupPos'][0]

    # if pa.units.enabled:
    if pa.util.use_paicos_quantities:
        r_max = 10000*center.unit_quantity
    else:
        r_max = 10000

    bins = np.linspace(0, r_max, 150)

    radial_filename = root_dir + '/data/radial_filename_247.hdf5'
    radial_profile = RadialProfiles(radial_filename,
                                    snap, center, r_max, bins)
    radial_profile.finalize()
