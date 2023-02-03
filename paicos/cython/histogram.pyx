import numpy as np
cimport numpy as np
from libc.math cimport log10

from cython.parallel import prange, parallel
cimport openmp


ctypedef fused real_t:
    float
    double
    np.float32_t
    np.float64_t


def get_hist_from_weights_and_idigit(int num_bins, real_t[:] weights,
                                     long[:] i_digit):

    cdef int Np = weights.shape[0]

    cdef real_t[:] hist = np.zeros(num_bins+1, dtype=np.float64)

    cdef int ip, ib
    for ip in range(Np):
        ib = i_digit[ip]
        hist[ib] = hist[ib] + weights[ip]

    # Return a numpy array instead of a view
    tmp = np.zeros(num_bins-1, dtype=np.float64)
    tmp[:] = hist[1:num_bins]
    return tmp


def get_hist2d_from_weights(real_t [:] xvec, real_t [:] yvec,
                            real_t [:] weights,
                            real_t lower_x, real_t upper_x, int nbins_x,
                            real_t lower_y, real_t upper_y, int nbins_y,
                            bint logspace,
                            int numthreads=1):

    assert numthreads == 1, 'use project_image_omp for more than one thread'

    # Number of particles
    cdef int Np = xvec.shape[0]

    # Create hist2d array
    cdef real_t[:, :] hist2d = np.zeros((nbins_x+1, nbins_y+1),
                                        dtype=np.float64)

    # Loop integers and other variables
    cdef int ip, ix=0, iy=0
    cdef real_t x, y, dx, dy
    cdef real_t log10lower_x = log10(lower_x)
    cdef real_t log10lower_y = log10(lower_y)

    if logspace:
        dx = nbins_x/(log10(upper_x)-log10(lower_x))
        dy = nbins_y/(log10(upper_y)-log10(lower_y))
    else:
        dx = nbins_x/(upper_x-lower_x)
        dy = nbins_y/(upper_y-lower_y)

    for ip in range(Np):
        x = xvec[ip]
        y = yvec[ip]
        if (x > lower_x) and (x < upper_x) and (y > lower_y) and (y < upper_y):
            if logspace:
                ix = <int> ((log10(x) - log10lower_x)*dx)
                iy = <int> ((log10(y) - log10lower_y)*dy)
            else:
                ix = <int> ((x - lower_x)*dx)
                iy = <int> ((y - lower_y)*dy)

        if (ix > 0) and (ix <= nbins_x) and (iy > 0) and (iy <= nbins_y):
            hist2d[ix, iy] += weights[ip]

    # Fix to avoid returning a memory-view
    tmp = np.zeros((nbins_x-1, nbins_y-1), dtype=np.float64)
    # tmp[:, :] = hist2d[:, :]
    tmp[:, :] = hist2d[1:nbins_x, 1:nbins_y]

    return tmp


def get_hist2d_from_weights_omp(real_t [:] xvec, real_t [:] yvec,
                                real_t [:] weights,
                                real_t lower_x, real_t upper_x, int nbins_x,
                                real_t lower_y, real_t upper_y, int nbins_y,
                                bint logspace,
                                int numthreads=1):

    # Number of particles
    cdef int Np = xvec.shape[0]

    cdef int threadnum

    cdef int nx = nbins_x + 1
    cdef int ny = nbins_y + 1

    # Create hist2d array
    cdef real_t[:, :] hist2d = np.zeros((nx, ny),
                                        dtype=np.float64)
    cdef real_t[:, :, :] tmp_variable = np.zeros((nx, ny, numthreads),
                                                 dtype=np.float64)

    # Loop integers and other variables
    cdef int ip, ix=0, iy=0
    cdef real_t x, y, dx, dy
    cdef real_t log10lower_x = log10(lower_x)
    cdef real_t log10lower_y = log10(lower_y)

    if logspace:
        dx = nbins_x/(log10(upper_x)-log10(lower_x))
        dy = nbins_y/(log10(upper_y)-log10(lower_y))
    else:
        dx = nbins_x/(upper_x-lower_x)
        dy = nbins_y/(upper_y-lower_y)

    with nogil, parallel(num_threads=numthreads):
        for ip in prange(Np, schedule='static'):
            threadnum = openmp.omp_get_thread_num()

            x = xvec[ip]
            y = yvec[ip]
            if (x > lower_x) and (x < upper_x) and (y > lower_y) and (y < upper_y):
                if logspace:
                    ix = <int> ((log10(x) - log10lower_x)*dx)
                    iy = <int> ((log10(y) - log10lower_y)*dy)
                else:
                    ix = <int> ((x - lower_x)*dx)
                    iy = <int> ((y - lower_y)*dy)

            if (ix > 0) and (ix <= nbins_x) and (iy > 0) and (iy <= nbins_y):
                tmp_variable[ix, iy, threadnum] = tmp_variable[ix, iy, threadnum] + weights[ip]

    # Add up contributions from each thread
    for threadnum in range(numthreads):
        for ix in range(nx):
            for iy in range(ny):
                hist2d[ix, iy] = hist2d[ix, iy] + tmp_variable[ix, iy, threadnum]

    # Fix to avoid returning a memory-view
    tmp = np.zeros((nbins_x-1, nbins_y-1), dtype=np.float64)
    # tmp[:, :] = hist2d[:, :]
    tmp[:, :] = hist2d[1:nbins_x, 1:nbins_y]

    return tmp


def find_normalizing_norm_of_2d_hist(real_t [:, :] hist2d, real_t[:] edges_x,
                                     real_t[:] edges_y):

    cdef int ix, iy
    cdef real_t dx, dy, cell_area
    cdef real_t norm = 0

    cdef int nx = hist2d.shape[0]
    cdef int ny = hist2d.shape[1]
    for ix in range(nx):
        for iy in range(ny):
            dx = edges_x[ix+1] - edges_x[ix]
            dy = edges_y[iy+1] - edges_y[iy]
            cell_area = dx*dy
            norm += hist2d[ix, iy]*cell_area
    return norm
