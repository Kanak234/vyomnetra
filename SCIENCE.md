# VYOMNETRA — Astrodynamics & Space Science Documentation

## 1. Orbital Propagation & Reference Frames
- **Primary Propagator**: SGP4 (Simplified General Perturbations 4) analytical propagator using Vallado (2006) implementation.
- **Reference Frame Standard**: SGP4 outputs vectors in the True Equator Mean Equinox (TEME) frame. Frame conversion pipeline transforms TEME -> ECEF (ITRF) -> WGS-84 Geodetic coordinates (Latitude, Longitude, Altitude above WGS-84 ellipsoid $a=6378.137\text{ km}, f=1/298.257223563$).
- **Relative Frame**: Hill-Clohessy-Wiltshire (HCW) equations operate in the Radial, In-track, Cross-track (RIC) frame centered on the primary target satellite.

## 2. Atmospheric Density & Decay Models
- **Density Engine**: Hybrid NRLMSISE-00 / Harris-Priester empirical model.
  - Primary atmospheric model: NRLMSISE-00 atmospheric density model driven by NOAA SWPC solar flux ($F_{10.7}$) and geomagnetic storm index ($K_p / A_p$).
  - System Fallback: Harris-Priester density interpolation table combined with exponential scale heights ($h_0 \in [100, 1000]\text{ km}$).
- **Re-Entry Monte Carlo**: 1,000-sample stochastic simulation varying drag coefficient ($B^* \sim \mathcal{N}(\mu, 0.15\mu)$) and solar activity ($F_{10.7} \sim \mathcal{N}(\mu, 0.20\mu)$). Yields 50% median re-entry date and 95% confidence window bounds.
- **Ground Track Footprint**: Sub-satellite ground path corridor calculated over final 3 orbital revolutions before re-entry interface ($h < 120\text{ km}$).

## 3. Conjunction & Collision Assessment
- **Foster 2D Algorithm**: Analytical reduction of 3D error covariance to 2D collision plane relative to hard-body collision radius ($R_{\text{HBR}}$).
- **Alfano 2D/3D Algorithm**: Numerical integration across error ellipse principal axes.
- **Patera Algorithm**: Polar contour line integration algorithm across relative position distribution.
- **Tri-Algorithm Stability**: Automatic raising of `PC_UNSTABLE` flag when max/min algorithm spread exceeds 10x.
- **Pc Max (Dilution Region)**: Maximizes probability of collision by finding optimal covariance scaling factor $k^* = d / (\sqrt{2} \sigma_{\text{avg}})$.

## 4. Debris Environment & Kessler Cascade
- **NASA Standard Breakup Model (SBM)**: Fragment count $N(L \ge L_c) = 0.1 M_{\text{total}}^{0.75} L_c^{-1.71}$ for cataclysmic collisions ($E/M \ge 40\text{ J/g}$) and $N(L \ge L_c) = 6.0 S^{0.75} L_c^{-1.71}$ for explosions.
- **Log-Normal Velocity Distribution**: $\log_{10}(\Delta V) = -0.06 \log_{10}(L_c) + 0.69$.
- **Spatial Density Binning**: 25 km altitude shells from 200 km to 2000 km in LEO.
