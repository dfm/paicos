import h5py
import numpy as np


class ImageCreator:

    def __init__(self, snap, center, widths, direction, npix=512,
                 numthreads=1):

        self.snap = snap

        from paicos import units

        if hasattr(center, 'unit'):
            self.center = center
        elif units.enabled:
            self.center = snap.converter.get_paicos_quantity(center,
                                                             'Coordinates')
        else:
            self.center = np.array(center)

        if hasattr(widths, 'unit'):
            self.widths = widths
        elif units.enabled:
            self.widths = snap.converter.get_paicos_quantity(widths,
                                                             'Coordinates')
        else:
            self.widths = np.array(widths)

        self.xc = self.center[0]
        self.yc = self.center[1]
        self.zc = self.center[2]
        self.width_x = self.widths[0]
        self.width_y = self.widths[1]
        self.width_z = self.widths[2]

        self.direction = direction

        self.npix = npix

        self.numthreads = numthreads

        if direction == 'x':
            self.extent = [self.yc - self.width_y/2, self.yc + self.width_y/2,
                           self.zc - self.width_z/2, self.zc + self.width_z/2]

        elif direction == 'y':
            self.extent = [self.xc - self.width_x/2, self.xc + self.width_x/2,
                           self.zc - self.width_z/2, self.zc + self.width_z/2]

        elif direction == 'z':
            self.extent = [self.xc - self.width_x/2, self.xc + self.width_x/2,
                           self.yc - self.width_y/2, self.yc + self.width_y/2]

        if units.enabled:
            self.extent = units.PaicosQuantity(self.extent, a=snap.a, h=snap.h)
        else:
            self.extent = np.array(self.extent)

        area = (self.extent[1]-self.extent[0])*(self.extent[3]-self.extent[2])
        self.area = area


class ArepoImage:
    """
    A derived data format for Arepo snapshots.

    A common task is to reduce Arepo snapshots to 2D arrays (either slices or
    projections) which can plotted as images. The computation of the 2D arrays
    can be time-consuming for high-resolution simulations with large
    snapshots. The purpose of this class is to define a derived data format
    which can be used to store images for later plotting with matplotlib.

    The creation of the 2D array is decoupled from this class, so that any
    custom method may be used (e.g. arepo-snap-util).

    """
    def __init__(self, image_filename, image_creator, mode='w'):

        """
        The filenames should include the full path:

        image_filename: e.g. "./projections/thin_projection_247_x.hdf5"

        snap: an instance of the Snapshot class

        If your image was created using a Paicos Projector or Slicer object. You can
        pass such an object using the image_creator input. Alternatively,
        you can simply

        center: A length-3 array giving the center of the image.

        widths: This is a length-3 array giving the widths of
                the image. For slices, the value indicating the thickness
                can be set to zero.

        direction: the viewing direction. Set this to e.g. 'x', 'y' or 'z'.

        """

        self.center = np.array(image_creator.center)
        self.widths = np.array(image_creator.widths)
        self.extent = np.array(image_creator.extent)
        self.direction = image_creator.direction

        self.mode = mode

        self.image_filename = image_filename
        tmp_list = image_filename.split('/')
        tmp_list[-1] = 'tmp_' + tmp_list[-1]
        self.tmp_image_filename = ''
        for ii in range(0, len(tmp_list)-1):
            self.tmp_image_filename += tmp_list[ii] + '/'
        self.tmp_image_filename += tmp_list[-1]
        self.arepo_snap_filename = image_creator.snap.first_snapfile_name

        # Create projection file and write information about image
        with h5py.File(self.tmp_image_filename, 'w') as f:
            f.create_group('image_info')
            f['image_info'].attrs['center'] = self.center
            f['image_info'].attrs['widths'] = self.widths
            f['image_info'].attrs['direction'] = self.direction
            f['image_info'].attrs['extent'] = self.extent

        self.copy_over_snapshot_information()

    def copy_over_snapshot_information(self):
        """
        Copy over attributes from the original arepo snapshot.
        In this way we will have access to units used, redshift etc
        """
        g = h5py.File(self.arepo_snap_filename, 'r')
        with h5py.File(self.tmp_image_filename, 'r+') as f:
            for group in ['Header', 'Parameters', 'Config']:
                f.create_group(group)
                for key in g[group].attrs.keys():
                    f[group].attrs[key] = g[group].attrs[key]
        g.close()

    def save_image(self, name, data, attrs=None):
        """
        This function saves a 2D image to the hdf5 file.
        """

        with h5py.File(self.tmp_image_filename, 'r+') as f:
            if hasattr(data, 'unit') and attrs is None:
                f.create_dataset(name, data=data.value)
                attrs = {'unit': data.unit.to_string()}
            else:
                f.create_dataset(name, data=data)
            if isinstance(attrs, dict):
                for key in attrs.keys():
                    f[name].attrs[key] = attrs[key]

    def add_group(self, name, attrs=None):
        with h5py.File(self.tmp_image_filename, 'r+') as f:
            f.create_group(name)
            if isinstance(attrs, dict):
                for key in attrs.keys():
                    f[name].attrs[key] = attrs[key]

    def add_data_to_group(self, groupname, dataname, data, attrs=None):
        data = np.array(data, dtype=np.float64)
        with h5py.File(self.tmp_image_filename, 'r+') as f:
            f[groupname].create_dataset(dataname, data=data)
            if isinstance(attrs, dict):
                for key in attrs.keys():
                    f[groupname][dataname].attrs[key] = attrs[key]

    def finalize(self):
        """
        """
        import os
        if self.mode == 'w':
            os.rename(self.tmp_image_filename, self.image_filename)
        elif self.mode == 'a' or self.mode == 'r+':
            with h5py.File(self.tmp_image_filename, 'r') as tmp:
                with h5py.File(self.image_filename, 'r+') as final:
                    np.testing.assert_array_equal(tmp['image_info'].attrs['center'],
                                                  final['image_info'].attrs['center'])
                    np.testing.assert_array_equal(tmp['image_info'].attrs['widths'],
                                                  final['image_info'].attrs['widths'])
                    assert tmp['image_info'].attrs['direction'] == final['image_info'].attrs['direction']
                    assert tmp['Header'].attrs['Time'] == final['Header'].attrs['Time']
                    for key in tmp.keys():
                        # Copy over group, its attributes, its datasets and their attributes
                        if isinstance(tmp[key], h5py._hl.group.Group):
                            if key not in final.keys():
                                final.create_group(key)
                                # Copy over group attributes
                                for g_attrs_key in tmp[key].attrs.keys():
                                    final[key].attrs[g_attrs_key] = tmp[key].attrs[g_attrs_key]
                                # Create data sets
                                for data_key in tmp[key].keys():
                                    final[key].create_dataset(data_key, data=tmp[key][data_key])
                                    # Copy over attributes for each data set
                                    for attrs_key in tmp[key][data_key].attrs.keys():
                                        final[key][data_key].attrs[attrs_key] = tmp[key][data_key].attrs[attrs_key]
                        # Copy over data set and its attributes
                        elif isinstance(tmp[key], h5py._hl.dataset.Dataset):
                            if key not in final.keys():
                                final.create_dataset(key, data=tmp[key])
                                for attrs_key in tmp[key].attrs.keys():
                                    final[key].attrs[attrs_key] = tmp[key].attrs[attrs_key]
            os.remove(self.tmp_image_filename)


if __name__ == '__main__':
    from paicos import root_dir
    from paicos import Snapshot

    image_filename = root_dir + "/data/test_arepo_image_format_247.hdf5"

    snap = Snapshot(root_dir + '/data/', 247)

    # A length-3 array giving the center of the image.
    center = [250000, 400000, 500000]

    # This is a length-3 array giving the widths of the image.
    widths = [10000, 10000, 2000]

    # The viewing direction. Set this to e.g. 'x', 'y' or 'z'.
    direction = 'z'

    # Using the base class for image creation
    image_creator = ImageCreator(snap, center, widths, direction)

    # Create arepo image file.
    # The file will have 'tmp_' prepended to the filename until .finalize()
    # is called.
    image_file = ArepoImage(image_filename, image_creator)

    # Save some images to the file (in a real example one would first import\\
    # and use a projection function)
    image_file.save_image('Density', np.random.random((200, 200)))
    image_file.save_image('Masses', np.random.random((400, 400)))
    image_file.save_image('Velocities', np.random.random((50, 40, 3)))

    # Move from temporary filename to final filename
    image_file.finalize()

    snap.load_data(0, 'Coordinates')
    # Now amend the file with another set of data
    image_file = ArepoImage(image_filename, image_creator, mode='a')
    data = np.random.random((500, 500))

    # Notice that we here also save attributes for coordinates,
    # these can be used to convert from comoving to non-comoving
    image_file.save_image('Coordinates', data,
                          attrs=snap.P_attrs['0_Coordinates'])

    # Let us also save information about the 10 most massive FOF groups
    # (sorted according to their M200_crit)
    image_file.add_group('Catalog', attrs={'Description': 'Most massive FOFs'})
    index = np.argsort(snap.Cat.Group['Group_M_Crit200'])[::-1]
    for key in snap.Cat.Group.keys():
        image_file.add_data_to_group('Catalog', key,
                                     snap.Cat.Group[key][index[:10]],
                                     attrs={'test of adding attrs': 1})

    image_file.finalize()

    with h5py.File(image_filename, 'r') as f:
        print(list(f.keys()))
        print(list(f['image_info'].keys()))
        print(dict(f['Coordinates'].attrs))
        print(list(f['Catalog'].keys()))
