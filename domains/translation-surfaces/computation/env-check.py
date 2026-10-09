"""Run by `env.py setup` inside the freshly installed conda env: the packages import and
a standard example computes. Exit 0 on success."""
import flatsurf
import surface_dynamics

print("sage-flatsurf", flatsurf.__version__)
print("surface_dynamics", surface_dynamics.version.version)
from flatsurf import translation_surfaces  # noqa: E402

S = translation_surfaces.mcmullen_L(1, 1, 1, 1)
print("stratum", S.stratum())
