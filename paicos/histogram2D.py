import numpy as np
from . import util
from . import settings


class Histogram2D:
    """
    This code defines a Histogram2D class which can be used to create 2D
    histograms. The class takes in the bin edges for the x and y axes, and an
    optional argument to indicate if the histogram should be in log scale. The
    class has methods to calculate the bin edges and centers, remove astro
    units, and create the histogram with a specific normalization. It also has
    a method to generate a color label for the histogram with units.
    """

    def __init__(self, snap, x, y, weights=None, bins_x=200, bins_y=200,
                 normalize=True, logscale=True):
        """
        Initialize the Histogram2D class with the bin edges for the x
        and y axes, and an optional argument to indicate if the
        histogram should be in log scale.

        Parameters:
            snap (Snapshot): the input snapshot

            x (array): The x data for the histogram

            y (array): The y data for the histogram

            weights (array): The weight data for the histogram, default
                             is None

            bins_x (tuple): Tuple of lower edge, upper edge and number
                            of bins for x axis. Alternatively an integer
                            denoting the number of bins spanning
                            x.min() to x.max().

            bins_y (tuple): Tuple of lower edge, upper edge and number
                            of bins for y axis. Alternatively an integer.

            normalize (bool): Indicates whether the histogram should be
                               normalized, default is True

            logscale (bool): Indicates whether to use logscale for the
                             histogram, default is True.


        """

        self.snap = snap

        if isinstance(x, str):
            self.x = snap[x]
        else:
            self.x = x

        if isinstance(y, str):
            self.y = snap[y]
        else:
            self.y = y

        if isinstance(weights, str):
            self.weights = snap[weights]
        else:
            self.weights = weights

        self.normalize = normalize

        if isinstance(bins_x, int):
            bins_x = [x.min(), x.max(), bins_x]

        if isinstance(bins_y, int):
            bins_y = [y.min(), y.max(), bins_y]

        self.logscale = logscale

        self.edges_x, self.centers_x = self._make_bins(bins_x)
        self.edges_y, self.centers_y = self._make_bins(bins_y)
        self.lower_x = self.edges_x[0]
        self.lower_y = self.edges_y[0]
        self.upper_x = self.edges_x[-1]
        self.upper_y = self.edges_y[-1]

        self.extent = [self.lower_x, self.upper_x, self.lower_y, self.upper_y]

        # check if OpenMP has any issues with the number of threads
        if util.check_if_omp_has_issues():
            self.use_omp = False
            self.numthreads = 1
        else:
            self.use_omp = True
            self.numthreads = settings.numthreads

        # Make the histogram
        self.hist2d = self._make_histogram()

    def _make_bins(self, bins):
        """
        Private method to calculate the edges and centers of the bins
        given lower, upper and number of bins.

        Parameters:
            bins (tuple): Tuple of lower edge, upper edge and number of
                          bins for the axis
        Returns:
            edges (array): Edges of the bins
            centers (array): Centers of the bins
        """

        lower, upper, nbins = bins
        edges, centers = self.__make_bins(lower, upper, nbins)
        from . import settings
        if settings.use_units:
            assert lower.unit == upper.unit
            edges = np.array(edges)*lower.unit_quantity
            centers = np.array(centers)*lower.unit_quantity
        return edges, centers

    @util.remove_astro_units
    def __make_bins(self, lower, upper, nbins):
        """
        Private method to calculate the edges and centers of the bins
        in logscale or linear scale based on the class variable logscale
        Parameters:
            lower (float): Lower edge of the bin
            upper (float): Upper edge of the bin
            nbins (int): Number of bins for the axis
        Returns:
            edges (array): Edges of the bins
            centers (array): Centers of the bins
        """

        if self.logscale:
            lower = np.log10(lower)
            upper = np.log10(upper)

        edges = lower + np.arange(nbins+1)*(upper-lower)/nbins
        centers = 0.5*(edges[1:] + edges[:-1])

        if self.logscale:
            edges = 10**edges
            centers = 10**centers

        return edges, centers

    def _find_norm(self, hist2d):
        """
        Private method to find the normalizing constant for the histogram
        Parameters:
            hist2d (2D array): The 2D histogram for which the normalizing
                               constant is needed
        Returns:
            norm (float): The normalizing constant
        """
        from .cython.histogram import find_normalizing_norm_of_2d_hist
        norm = find_normalizing_norm_of_2d_hist(hist2d, self.edges_x,
                                                self.edges_y)
        return norm

    def get_colorlabel(self, x_symbol, y_symbol, weight_symbol=None):
        """
        Method to generate a color label for the histogram with units
        Parameters:
            x_symbol (string): Symbol for x axis
            y_symbol (string): Symbol for y axis
            weight_symbol (string): Symbol for weight of the histogram,
                                    default is None
        Returns:
            colorlabel (string): The color label for the histogram with
                                 units
        """
        from . import settings

        assert settings.use_units

        unit_label = self.hist_units.to_string(format='latex')[1:-1]
        unit_label = r'[' + unit_label + r']'

        if self.logscale:
            colorlabel = (r'/\left(\mathrm{d}\mathrm{log}_{10} ' + x_symbol +
                          r'\,\mathrm{d}\mathrm{log}_{10}' +
                          y_symbol + r'\right)'
                          + r'\;' + unit_label)
        else:
            colorlabel = (r'/\left(\mathrm{d}' + x_symbol +
                          r'\,\mathrm{d}' + y_symbol + r'\right)'
                          + r'\;' + unit_label)

        if weight_symbol is not None:
            if self.normalize:
                colorlabel = weight_symbol + \
                    r'_\mathrm{tot}^{-1}\,\mathrm{d}' + \
                    weight_symbol + colorlabel
            else:
                colorlabel = r'\mathrm{d}' + weight_symbol + colorlabel
        else:
            if self.normalize:
                colorlabel = r'\mathrm{pixel count}/\mathrm{total count}' + colorlabel
            else:
                colorlabel = r'\mathrm{pixel count}' + colorlabel
        self.colorlabel = (r'$' + colorlabel + r'$')
        return self.colorlabel

    @util.remove_astro_units
    def _cython_make_histogram(self, x, y, edges_x, edges_y, weights):

        if self.use_omp:
            from .cython.histogram import get_hist2d_from_weights_omp
            get_hist2d_from_weights = get_hist2d_from_weights_omp
        else:
            from .cython.histogram import get_hist2d_from_weights

        nbins_x = edges_x.shape[0] - 1
        nbins_y = edges_y.shape[0] - 1

        lower_x = edges_x[0]
        upper_x = edges_x[-1]
        lower_y = edges_y[0]
        upper_y = edges_y[-1]

        hist2d = get_hist2d_from_weights(
            x, y, weights,
            lower_x, upper_x, nbins_x,
            lower_y, upper_y, nbins_y,
            self.logscale,
            numthreads=1)

        return hist2d

    def _make_histogram(self):
        """
        Private method to create the 2D histogram.

        Returns:
            hist2d (2D array): The 2D histogram
        """
        from . import settings
        from astropy import units as u

        x = self.x
        y = self.y
        weights = self.weights
        normalize = self.normalize

        # Figure out units for the histogram
        if settings.use_units:
            if not normalize and (weights is not None):
                hist_units = weights.unit
            else:
                hist_units = u.Unit('')
            if self.logscale:
                hist_units *= u.Unit('dex')**(-2)
            else:
                hist_units /= x.unit*y.unit

            self.hist_units = hist_units

            assert x.unit == self.edges_x.unit
            assert y.unit == self.edges_y.unit

        if weights is None:
            weights = np.ones_like(x, dtype=np.float64)

        hist2d = self._cython_make_histogram(x, y, self.edges_x,
                                             self.edges_y, weights)

        if normalize:
            hist2d /= self._find_norm(hist2d)

        hist2d = hist2d.T

        if settings.use_units:
            from . import units as pu
            hist2d = pu.PaicosQuantity(hist2d, self.hist_units, a=self.x.a,
                                       h=self.x.h)
        return hist2d

    def copy_over_snapshot_information(self, filename):
        """
        Copy over attributes from the original arepo snapshot.
        In this way we will have access to units used, redshift etc
        """
        import h5py
        g = h5py.File(self.snap.first_snapfile_name, 'r')
        with h5py.File(filename, 'r+') as f:
            for group in ['Header', 'Parameters', 'Config']:
                f.create_group(group)
                for key in g[group].attrs.keys():
                    f[group].attrs[key] = g[group].attrs[key]
        g.close()

    def save(self, basedir, basename="2d_histogram"):
        import h5py

        if basedir[-1] != '/':
            basedir += '/'

        snapnum = self.snap.snapnum
        filename = basedir + basename + '_{:03d}.hdf5'.format(snapnum)
        with h5py.File(filename, 'w') as hdf5file:
            #
            hdf5file.create_group('hist_info')
            hdf5file['hist_info'].attrs['logscale'] = self.logscale
            hdf5file['hist_info'].attrs['normalize'] = self.normalize

            util.save_dataset(hdf5file, 'centers_x', self.centers_x)
            util.save_dataset(hdf5file, 'centers_y', self.centers_y)
            data = self.hist2d
            name = 'hist2d'
            attrs = {}
            if hasattr(data, 'unit'):
                hdf5file.create_dataset(name, data=data.value)
                attrs.update({'unit': self.hist2d.unit.to_string()})
            else:
                hdf5file.create_dataset(name, data=data)
            try:
                attrs.update({'colorlabel': self.colorlabel})
            except AttributeError:
                print(("Unable to save colorlabel, please call " +
                      "the 'get_colorlabel' method before saving."))
            # Add attributes
            for key in attrs.keys():
                hdf5file[name].attrs[key] = attrs[key]

        self.copy_over_snapshot_information(filename)