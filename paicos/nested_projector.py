"""
Defines a class that creates an image of a given variable by projecting it
onto a 2D plane using nested grids.
"""
import numpy as np
from . import settings
from .projector import Projector
from .util import remove_astro_units
from .cython.sph_projectors import project_image, project_image_omp


class NestedProjector(Projector):
    """
    This implements an SPH-like projection of gas variables using nested grids.
    """

    def __init__(self, snap, center, widths, direction,
                 npix=512, nvol=8, factor=3, npix_min=128,
                 verbose=False, make_snap_with_selection=True,
                 store_subimages=False):

        super().__init__(snap, center, widths, direction,
                         npix=npix, nvol=nvol,
                         make_snap_with_selection=make_snap_with_selection)

        self.verbose = verbose
        self.store_subimages = store_subimages

        # Code specific for nested functionality below
        self.factor = factor
        self.npix_min = npix_min

        # Find required grid resolutions and the binning in smoothing (hsml)
        bins, n_grids = self._get_bins(self.extent[1] - self.extent[0])

        # Digitize particles (make OpenMP cython version of this?)
        digitize = remove_astro_units(np.digitize)
        i_digit = digitize(self.hsml, bins=bins)
        n_particles = self.hsml.shape[0]
        count = 0
        for ii, n_grid in enumerate(n_grids):
            index = i_digit == (ii + 1)
            count += np.sum(index)
            if self.verbose:
                print(f'n_grid={n_grid} contains {np.sum(index)} particles')

        assert n_particles == count, 'need to include all cells!'

        self.n_grids = n_grids
        self.i_digit = i_digit

    @remove_astro_units
    def _get_bins(self, width):

        @remove_astro_units
        def nearest_power_of_two(x):
            return int(2**np.ceil(np.log2(x)))

        def log2int(x):
            return int(np.log2(x))

        npix_low = nearest_power_of_two(width / np.max(self.hsml) * self.factor)
        npix_high = nearest_power_of_two(width / np.min(self.hsml) * self.factor)

        npix_high = min(npix_high, self.npix)
        npix_low = max(npix_low, self.npix_min)
        npix_low = min(npix_low, npix_high)

        n_grids = []
        bins = [width]
        for ii in range(log2int(npix_low), log2int(npix_high) + 1):
            n_grid = 2**ii

            if self.verbose:
                print(n_grid, width / n_grid)
            n_grids.append(n_grid)
            if n_grid == npix_high:
                bins.append(0.0)
            else:
                bins.append(width / n_grid * self.factor)

        return bins, n_grids

    def increase_image_resolution(self, image, factor):
        """
        Increase the number of pixes without changing the total 'mass'
        of the image
        """
        if factor == 1:
            return image
        repeats = factor
        new_image = np.repeat(np.repeat(image, repeats, axis=0),
                              repeats, axis=1)
        return new_image / factor**2

    def sum_contributions(self, images):
        """
        Given the list of images at various resolutions, sum them up.
        """
        full_image = np.zeros(images[-1].shape)
        n = images[-1].shape[0]
        for image in images:
            full_image += self.increase_image_resolution(image,
                                                         n // image.shape[0])

        return full_image

    @remove_astro_units
    def _cython_project(self, center, widths, variable):
        if settings.openMP_has_issues:
            from .cython.sph_projectors import project_image as project
        else:
            from .cython.sph_projectors import project_image_omp as project

        x_c, y_c, z_c = center[0], center[1], center[2]
        width_x, width_y, width_z = widths

        boxsize = self.snap.box

        images = []
        for ii, n_grid in enumerate(self.n_grids):
            index_n = self.i_digit == (ii + 1)
            hsml_n = self.hsml[index_n]
            pos_n = self.pos[index_n]
            variable_n = variable[index_n]
            if self.direction == 'x':
                proj_n = project(pos_n[:, 1],
                                 pos_n[:, 2],
                                 variable_n,
                                 hsml_n, n_grid,
                                 y_c, z_c, width_y, width_z,
                                 boxsize, settings.numthreads_reduction)
            elif self.direction == 'y':
                proj_n = project(pos_n[:, 0],
                                 pos_n[:, 2],
                                 variable_n,
                                 hsml_n, n_grid,
                                 x_c, z_c, width_x, width_z,
                                 boxsize, settings.numthreads_reduction)
            elif self.direction == 'z':
                proj_n = project(pos_n[:, 0],
                                 pos_n[:, 1],
                                 variable_n,
                                 hsml_n, n_grid,
                                 x_c, y_c, width_x, width_y,
                                 boxsize, settings.numthreads_reduction)
            images.append(proj_n)

        projection = self.sum_contributions(images)

        if self.store_subimages:
            self.images = images

        return projection
