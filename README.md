# Supplementary material: Post-Quantum Key Establishment over MAVLink

Supplementary material of the manuscript *Post-Quantum Key Establishment over MAVLink: Measured Cost and Integration Pitfalls of HQC on a Small UAV*, submitted to IEEE Transactions on Aerospace and Electronic
Systems (resubmission of TAES-2026-2045), by Nicolás Segura Castro, Carlos David Casadiego, Javier Vera, Valérie Gauthier-Umaña (Universidad de los Andes).

The scripts, test programs, recorded outputs, patch and documents are in [`supplementary/`](supplementary/);
its [README](supplementary/README.md) says which script regenerates each figure of the manuscript and how to
run them. The evaluated firmware and the packet captures are **not** in this repository: they are the ArduPilot
fork at commit `b402392` of [`cdcp2/ardupilot_post_quantum_kem`](https://github.com/cdcp2/ardupilot_post_quantum_kem/tree/b4023923c08dacbaf959f62825a1152c0e4d0870), cloned with `--recursive`, which the
manuscript cites. The ground-station software was not archived.

## Citing

See [`CITATION.cff`](CITATION.cff). Once this repository is archived on Zenodo, cite the DOI of the release.

## License

GPL-3.0 (`LICENSE`): the patch in `supplementary/corrections/` modifies ArduPilot, which is GPL-3.0, and the
rest of the material is released under the same terms.

## Minting the Zenodo DOI (for the maintainer)

1. Make the repository public (Settings, Danger Zone, Change visibility).
2. In <https://zenodo.org/account/settings/github/>, sign in with GitHub and switch this repository on.
3. On GitHub, create a release from tag `v1.0.0` (Releases, Draft a new release, choose the tag, publish). Zenodo
   archives the release within minutes and mints the DOI, taking the metadata from `.zenodo.json`.
4. The DOI appears in the Zenodo GitHub page and in the record; it is the one to give in the submission form.
