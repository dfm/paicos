import paicos as pa
import numpy as np

import matplotlib.pyplot as plt

plt.figure(1)
plt.clf()
fig, axes = plt.subplots(num=1, ncols=3, sharex=True)
for ii in range(2):
    snap = pa.Snapshot(pa.root_dir + "/data", 247)
    center = snap.Cat.Group["GroupPos"][0]

    pos = snap["0_Coordinates"]

    r = np.sqrt(np.sum((pos - center[None, :]) ** 2.0, axis=1))

    if pa.settings.use_units:
        r_max = 10000 * r.unit_quantity
    else:
        r_max = 10000

    index = r < r_max * 1.1

    bins = np.linspace(0, r_max, 150)

    # Rewrite to use same syntax for bins as the 2D histogram
    # bins = np.logspace(-2, np.log10(r_max), 1000)

    B2 = np.sum((snap["0_MagneticField"]) ** 2, axis=1)
    Volumes = snap["0_Volumes"]
    Masses = snap["0_Masses"]
    Temperatures = snap["0_Temperatures"]

    if ii == 0:
        h_r = pa.Histogram(r[index], bins, verbose=True)
        B2TimesVolumes = h_r.hist((B2 * Volumes)[index])
        Volumes = h_r.hist(Volumes[index])
        TTimesMasses = h_r.hist((Masses * Temperatures)[index])
        Masses = h_r.hist(Masses[index])

        axes[0].loglog(h_r.bin_centers, Masses / Volumes)
        axes[1].loglog(h_r.bin_centers, B2TimesVolumes / Volumes)
        axes[2].loglog(h_r.bin_centers, TTimesMasses / Masses)

        if pa.settings.use_units:
            axes[0].set_xlabel(h_r.bin_centers.label(r"\mathrm{radius}\;"))
            axes[0].set_ylabel((Masses / Volumes).label("\\rho"))
            axes[1].set_ylabel((B2TimesVolumes / Volumes).label("B^2"))
            axes[2].set_ylabel((TTimesMasses / Masses).label("T"))
    else:
        B2TimesVolumes, edges = np.histogram(
            r[index], weights=(B2 * Volumes)[index], bins=bins
        )

        Volumes, edges = np.histogram(r[index], weights=Volumes[index], bins=bins)

        TTimesMasses, edges = np.histogram(
            r[index], weights=(Masses * Temperatures)[index], bins=bins
        )

        Masses, edges = np.histogram(r[index], weights=Masses[index], bins=bins)

        bin_centers = 0.5 * (edges[1:] + edges[:-1])

        axes[0].loglog(bin_centers, Masses / Volumes, "--")
        axes[1].loglog(bin_centers, B2TimesVolumes / Volumes, "--")
        axes[2].loglog(bin_centers, TTimesMasses / Masses, "--")

plt.show()