'''
 SiP.py - A library of different silicon photonic device compact models
 leveraging artificial neural networks

Changes                                       (Author) (Date)
  Initilization .............................. (AMH) - 22-01-2019

Current devices:                              (Author)(Date last modified)
  Straight waveguide (TE/TM) ................. (AMH) - 22-01-2019
  Bent waveguide ............................. (AMH) - 22-01-2019
  Evanescent waveguide coupler ............... (AMH) - 22-01-2019
  Racetrack ring resonator ................... (AMH) - 22-01-2019
  Rectangular ring resonator ................. (AMH) - 22-01-2019

'''

# ---------------------------------------------------------------------------- #
# Import libraries
# ---------------------------------------------------------------------------- #
from SiPANN import import_nn
import numpy as np
import skrf as rf
import pkg_resources
from scipy.signal import find_peaks, peak_widths
from scipy.interpolate import UnivariateSpline
import joblib
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline

# ---------------------------------------------------------------------------- #
# Initialize ANNs
# ---------------------------------------------------------------------------- #

'''
We initialize all of the ANNs as global objects for speed. This is especially
useful for optimization routines and GUI's that need to make several ANN
evaluations quickly.
'''

gap_FILE = pkg_resources.resource_filename('SiPANN', 'ANN/TIGHT_ANGLE_GAP')
ANN_gap      = import_nn.ImportNN(gap_FILE)

straight_FILE = pkg_resources.resource_filename('SiPANN', 'ANN/TIGHT_ANGLE_STRAIGHT')
ANN_straight = import_nn.ImportNN(straight_FILE)

bent_FILE = pkg_resources.resource_filename('SiPANN', 'ANN/TIGHT_ANGLE_BENT_RAND')
ANN_bent = import_nn.ImportNN(bent_FILE)

'''
Let's initialize all of the linear regression functions.
'''

gap_FILE = pkg_resources.resource_filename('SiPANN', 'LR/R_gap.joblib')
LR_gap = joblib.load(gap_FILE)

straight_FILE = pkg_resources.resource_filename('SiPANN', 'LR/R_straight.joblib')
LR_straight = joblib.load(straight_FILE)

bent_FILE = pkg_resources.resource_filename('SiPANN', 'LR/R_bent.joblib')
LR_bent = joblib.load(bent_FILE)

# ---------------------------------------------------------------------------- #
# Helper functions
# ---------------------------------------------------------------------------- #

# Generalized N-dimensional products. Useful for "vectorizing" the ANN calculations
# with multiple inputs
def cartesian_product(arrays):
    la = len(arrays)
    dtype = np.find_common_type([a.dtype for a in arrays], [])
    arr = np.empty([len(a) for a in arrays] + [la], dtype=dtype)
    for i, a in enumerate(np.ix_(*arrays)):
        arr[..., i] = a
    return arr.reshape(-1, la)

# ---------------------------------------------------------------------------- #
# Strip waveguide
# ---------------------------------------------------------------------------- #

'''
straightWaveguide()

Calculates the first three effective index values of the TE and TM modes. Can also
calculate derivatives with respect to any of the inputs. This is especially useful
for calculating the group index, or running gradient based optimization routines.

Each of the inputs can either be a one dimensional numpy array or a scalar. This
is especially useful if you want to sweep over multiple parameters and include
all of the possible permutations of the sweeps.

The output is a multidimensional array. The size of each dimension corresponds with
the size of each of the inputs, such that
   DIM1 = size(wavelength)
   DIM2 = size(width)
   DIM3 = size(thickness)

So if I swept 100 wavelength points, 1 width, and 10 possible thicknesses, then
the dimension of each output effective index (or higher order derivative) would
be: (100,1,10).

INPUTS:
wavelength .............. [np array](N,) wavelength points to evaluate
width ................... [np array](N,) width of the waveguides in microns
thickness ............... [np array](N,) thickness of the waveguides in microns
derivative .............. [scalar] (default=None) Order of the derivative to take

OUTPUTS:
TE0 .................... [np array](N,M,P) First TE effective index (or derivative)
TE1 .................... [np array](N,M,P) Second TE effective index (or derivative)
TE2 .................... [np array](N,M,P) Third TE effective index (or derivative)
TM0 .................... [np array](N,M,P) First TM effective index (or derivative)
TM1 .................... [np array](N,M,P) Second TM effective index (or derivative)
TM2 .................... [np array](N,M,P) Third TM effective index (or derivative)

'''
def straightWaveguide(wavelength,width,thickness,angle,derivative=None):

    # Santize the input
    if type(wavelength) is np.ndarray:
        wavelength = np.squeeze(wavelength)
    else:
        wavelength = np.array([wavelength])
    if type(width) is np.ndarray:
        width = np.squeeze(width)
    else:
        width = np.array([width])
    if type(thickness) is np.ndarray:
        thickness = np.squeeze(thickness)
    else:
        thickness = np.array([thickness])
    if type(angle) is np.ndarray:
        angle = np.squeeze(angle)
    else:
        angle = np.array([angle])

    # Run through neural network
    INPUT  = cartesian_product([wavelength,width,thickness,angle])

    if derivative is None:
        OUTPUT = LR_straight.predict(INPUT)
    else:
        numRows = INPUT.shape[0]
        OUTPUT = np.zeros((numRows,12))
        # Loop through the derivative of all the outputs
        for k in range(12):
            OUTPUT[:,k] = np.squeeze(ANN_straight.differentiate(INPUT,d=(k,0,derivative)))

    # process the output
    '''
    tensorSize = (wavelength.size,width.size,thickness.size)
    TE0 = np.reshape(OUTPUT[:,0],tensorSize) + 1j*np.reshape(OUTPUT[:,6],tensorSize)
    TE1 = np.reshape(OUTPUT[:,1],tensorSize) + 1j*np.reshape(OUTPUT[:,7],tensorSize)
    TE2 = np.reshape(OUTPUT[:,2],tensorSize) + 1j*np.reshape(OUTPUT[:,8],tensorSize)
    TM0 = np.reshape(OUTPUT[:,3],tensorSize) + 1j*np.reshape(OUTPUT[:,9],tensorSize)
    TM1 = np.reshape(OUTPUT[:,4],tensorSize) + 1j*np.reshape(OUTPUT[:,10],tensorSize)
    TM2 = np.reshape(OUTPUT[:,5],tensorSize) + 1j*np.reshape(OUTPUT[:,11],tensorSize)

    return TE0,TE1,TE2,TM0,TM1,TM2
    '''
    tensorSize = (wavelength.size,width.size,thickness.size)
    TE0 = OUTPUT#np.reshape(OUTPUT[:,0],tensorSize)# + 1j*np.reshape(OUTPUT[:,1],tensorSize)
    return TE0

'''
straightWaveguide_S()

Calculates the analytic scattering matrix of a simple straight waveguide with
length L.

INPUTS:
wavelength .............. [np array](N,) wavelength points to evaluate
width ................... [scalar] width of the waveguides in microns
thickness ............... [scalar] thickness of the waveguides in microns
L ....................... [scalar] length of the waveguide in microns

OUTPUTS:
S ....................... [np array](N,2,2) scattering matrix for each wavelength


'''
def straightWaveguide_S(wavelength,width,thickness,length):

    TE0,TE1,TE2,TM0,TM1,TM2 = straightWaveguide(wavelength,width,thickness)

    neff = np.squeeze(TE0)

    N = wavelength.shape[0]
    S = np.zeros((N,2,2),dtype='complex128')
    S[:,0,1] = np.exp(1j*2*np.pi*length*neff/wavelength)
    S[:,1,0] = np.exp(1j*2*np.pi*length*neff/wavelength)
    return S

# ---------------------------------------------------------------------------- #
# Bent waveguide
# ---------------------------------------------------------------------------- #
'''
bentWaveguide()

Calculates the analytic scattering matrix of a simple, parallel waveguide
directional coupler using the ANN.

INPUTS:
wavelength .............. [np array](N,) wavelength points to evaluate
gap ..................... [scalar] gap in the coupler region in microns
width ................... [scalar] width of the waveguides in microns
thickness ............... [scalar] thickness of the waveguides in microns
length .................. [scalar] length of the waveguide in microns

OUTPUTS:
S ....................... [np array](N,2,2) Scattering matrix

'''
def bentWaveguide(wavelength,width,thickness,radius,angle,derivative=None):

    # Santize the input
    if type(wavelength) is np.ndarray:
        wavelength = np.squeeze(wavelength)
    else:
        wavelength = np.array([wavelength])
    if type(width) is np.ndarray:
        width = np.squeeze(width)
    else:
        width = np.array([width])
    if type(thickness) is np.ndarray:
        thickness = np.squeeze(thickness)
    else:
        thickness = np.array([thickness])
    if type(radius) is np.ndarray:
        radius = np.squeeze(radius)
    else:
        radius = np.array([radius])
    if type(angle) is np.ndarray:
        angle = np.squeeze(angle)
    else:
        angle = np.array([angle])

    # Run through neural network
    INPUT  = cartesian_product([wavelength,width,thickness,radius,angle])

    if derivative is None:
        OUTPUT = LR_bent.predict(INPUT)
    else:
        numRows = INPUT.shape[0]
        OUTPUT = np.zeros((numRows,2))
        # Loop through the derivative of all the outputs
        for k in range(2):
            OUTPUT[:,k] = np.squeeze(ANN_bent.differentiate(INPUT,d=(k,0,derivative)))

    # process the output
    tensorSize = (wavelength.size,width.size,thickness.size,radius.size)
    TE0 = OUTPUT#np.reshape(OUTPUT[:,0],tensorSize)# + 1j*np.reshape(OUTPUT[:,1],tensorSize)

    return TE0

def bentWaveguide_S(wavelength,radius,width,thickness,gap,angle):

    # Pull effective indices from ANN
    TE0 = bentWaveguide(wavelength,width,thickness,radius)
    neff = np.squeeze(TE0)

    N = wavelength.shape[0]
    S = np.zeros((N,2,2),dtype='complex128')
    S[:,0,1] = np.exp(1j*2*np.pi*radius*neff*angle/wavelength)
    S[:,1,0] = np.exp(1j*2*np.pi*radius*neff*angle/wavelength)
    return S

# ---------------------------------------------------------------------------- #
# Evanescent waveguide coupler
# ---------------------------------------------------------------------------- #
'''
evWGcoupler()

Calculates the analytic scattering matrix of a simple, parallel waveguide
directional coupler using the ANN.

INPUTS:
wavelength .............. [np array](N,) wavelength points to evaluate
couplerLength ........... [scalar] length of the coupling region in microns
gap ..................... [scalar] gap in the coupler region in microns
width ................... [scalar] width of the waveguides in microns
thickness ............... [scalar] thickness of the waveguides in microns

OUTPUTS:
S ....................... [np array](N,4,4) Scattering matrix

'''

def evWGcoupler(wavelength,width,thickness,gap,angle,derivative=None):

    # Santize the input
    if type(wavelength) is np.ndarray:
        wavelength = np.squeeze(wavelength)
    else:
        wavelength = np.array([wavelength])
    if type(width) is np.ndarray:
        width = np.squeeze(width)
    else:
        width = np.array([width])
    if type(thickness) is np.ndarray:
        thickness = np.squeeze(thickness)
    else:
        thickness = np.array([thickness])
    if type(gap) is np.ndarray:
        gap = np.squeeze(gap)
    else:
        gap = np.array([gap])
    if type(angle) is np.ndarray:
        angle = np.squeeze(angle)
    else:
        angle = np.array([angle])

    # Run through neural network
    INPUT  = cartesian_product([wavelength,width,thickness,gap,angle])

    if derivative is None:
        OUTPUT0 = LR_gap[0].predict(INPUT)
        OUTPUT1 = LR_gap[1].predict(INPUT)
    else:
        numRows = INPUT.shape[0]
        OUTPUT = np.zeros((numRows,4))
        # Loop through the derivative of all the outputs
        for k in range(4):
            OUTPUT[:,k] = np.squeeze(ANN_gap.differentiate(INPUT,d=(k,0,derivative)))

    # process the output
    tensorSize = (wavelength.size,width.size,thickness.size,gap.size)
    TE0 = OUTPUT0#np.reshape(OUTPUT0[:,0],tensorSize)# + 1j*np.reshape(OUTPUT[:,2],tensorSize)
    TE1 = OUTPUT1#np.reshape(OUTPUT1[:,1],tensorSize)# + 1j*np.reshape(OUTPUT[:,3],tensorSize)

    return TE0,TE1

def evWGcoupler_S(wavelength,width,thickness,gap,couplerLength):
    N = wavelength.shape[0]

    # Get the fundamental mode of the waveguide itself
    TE0,TE1,TE2,TM0,TM1,TM2 = straightWaveguide(wavelength,width,thickness)
    n0 = np.squeeze(TE0)

    # Get the modes of the coupler structure
    cTE0,cTE1 = evWGcoupler(wavelength,width,thickness,gap)
    n1 = np.squeeze(cTE0)     # Get the first mode of the coupler region
    n2 = np.squeeze(cTE1)     # Get the second mode of the coupler region
    dn = n1 - n2  # Find the modal differences
    # -------- Formulate the S matrix ------------ #
    #x =  np.exp(-1j*2*np.pi*n0*couplerLength/wavelength) * np.cos(np.pi*dn/wavelength*couplerLength)
    #y =  1j * np.exp(-1j*2*np.pi*n0*couplerLength/wavelength) * np.sin(np.pi*dn/wavelength*couplerLength)

    Beta1 = 2*np.pi*n1 / wavelength
    Beta2 = 2*np.pi*n2 / wavelength
    x = 1/np.sqrt(4) * (np.exp(1j*Beta1*couplerLength) + np.exp(1j*Beta2*couplerLength))
    y = 1/np.sqrt(4) * (np.exp(1j*Beta1*couplerLength) + np.exp(1j*Beta2*couplerLength - 1j*np.pi))

    S = np.zeros((N,4,4),dtype='complex128')

    # Row 1
    S[:,0,1] = x
    S[:,0,3] = y
    # Row 2
    S[:,1,0] = x
    S[:,1,2] = y
    # Row 3
    S[:,2,1] = y
    S[:,2,3] = x
    # Row 4
    S[:,3,0] = y
    S[:,3,2] = x
    return S
# ---------------------------------------------------------------------------- #
# Racetrack Ring Resonator
# ---------------------------------------------------------------------------- #

'''
racetrackRR()

This particular transfer function assumes that the coupling sides of the ring
resonator are straight, and the other two sides are curved. Therefore, the
roundtrip length of the RR is 2*pi*radius + 2*couplerLength.

We assume that the round parts of the ring have negligble coupling compared to
the straight sections.

INPUTS:
wavelength .............. [np array](N,) wavelength points to evaluate
radius .................. [scalar] radius of the sides in microns
couplerLength ........... [scalar] length of the coupling region in microns
gap ..................... [scalar] gap in the coupler region in microns
width ................... [scalar] width of the waveguides in microns
thickness ............... [scalar] thickness of the waveguides in microns

OUTPUTS:
S ....................... [np array](N,4,4) Scattering matrix

'''
def racetrack_AP_RR(wavelength,radius=5,couplerLength=5,gap=0.2,width=0.5,thickness=0.2):

    # Sanitize the input
    wavelength = np.squeeze(wavelength)
    N          = wavelength.shape[0]

    # Calculate coupling scattering matrix
    couplerS = evWGcoupler_S(wavelength,width,thickness,gap,couplerLength)

    # Calculate bent scattering matrix
    bentS = bentWaveguide_S(wavelength,radius,width,thickness,gap,np.pi)

    # Calculate straight scattering matrix
    straightS = straightWaveguide_S(wavelength,width,thickness,couplerLength)

    # Cascade all the waveguide sections
    Sw = rf.connect_s(bentS, 1, straightS, 0)
    Sw = rf.connect_s(Sw, 1, bentS, 0)

    # Connect coupler to waveguide section
    S = rf.connect_s(couplerS, 2, Sw, 0)

    # Close the ring
    S = rf.innerconnect_s(S, 2,3)

    ## Cascade final coupler
    #S = rf.connect_s(S, 2, couplerS, 2)
    #S = rf.innerconnect_s(S, 2,5)

    # Output final s matrix
    return S

def racetrack_AP_RR_TF(wavelength,angle=90,radius=12,couplerLength=4.5,gap=0.2,width=0.5,thickness=0.2,widthCoupler=0.5,loss=[0.99],coupling=[0]):

    # Sanitize the input
    wavelength = np.squeeze(wavelength)
    N          = wavelength.shape[0]

    # calculate coupling
    cTE0,cTE1 = evWGcoupler(wavelength=wavelength,width=widthCoupler,thickness=thickness,angle=angle,gap=gap)
    n1 = np.squeeze(cTE0)     # Get the first mode of the coupler region
    n2 = np.squeeze(cTE1)     # Get the second mode of the coupler region
    Beta1 = 2*np.pi*n1 / wavelength
    Beta2 = 2*np.pi*n2 / wavelength
    x = 0.5 * (np.exp(1j*Beta1*couplerLength) + np.exp(1j*Beta2*couplerLength))
    y = 0.5 * (np.exp(1j*Beta1*couplerLength) + np.exp(1j*Beta2*couplerLength - 1j*np.pi))

    alpha_c = np.sqrt(np.abs(x) ** 2 + np.abs(y) ** 2)

    t_c = x
    k_c = y


    # Construct the coupling polynomial
    couplingPoly = np.poly1d(coupling)

    r = np.abs(x) - couplingPoly(wavelength)
    k = np.abs(y)

    # calculate bent waveguide
    TE0_B = np.squeeze(bentWaveguide(wavelength=wavelength,width=width,thickness=thickness,angle=angle,radius=radius))

    # calculate straight waveguide
    TE0 = np.squeeze(straightWaveguide(wavelength=wavelength,width=width,thickness=thickness,angle=angle))

    # Calculate round trip length
    L = 2*np.pi*radius + 2*couplerLength

    # calculate total loss
    #alpha = np.squeeze(np.exp(- np.imag(TE0) * 2*couplerLength - np.imag(TE0_B)*2*np.pi*radius - lossPoly(wavelength)*L))
    alpha_t = (np.exp(-np.imag(TE0) * 2*couplerLength - np.imag(TE0_B)*2*np.pi*radius))
    alpha_m  = np.squeeze(alpha_c * alpha_t)
    offset = np.mean(alpha_m)
    lossTemp = loss.copy()
    lossTemp[-1] = loss[-1] - (1-offset)
    lossPoly = np.poly1d(loss)
    alpha = lossPoly(wavelength)
    alpha_s = alpha - alpha_m

    # calculate phase shifts
    phi_c        = np.unwrap(np.angle(t_c))
    BetaStraight = np.unwrap(2*np.pi*np.real(TE0) / wavelength)
    BetaBent     = np.unwrap(2*np.pi*np.real(TE0_B) / wavelength)
    phi_r        = np.squeeze( BetaStraight * couplerLength + BetaBent*2*np.pi*radius)
    phi          = np.unwrap(phi_r + phi_c)

    t = np.abs(t_c) / alpha_c

    ## Cascade final coupler
    #E = np.exp(1j*(np.pi+phi)) * (alpha - r*np.exp(-1j*phi))/(1-r*alpha*np.exp(1j*phi))
    E = (t - alpha * np.exp(1j*phi)) / (1-alpha*t*np.exp(1j*phi)) * (t_c / np.conj(t_c)) * alpha_c * np.exp(-1j * phi_c)

    # Output final s matrix
    return E, alpha, t, alpha_s, phi
# ---------------------------------------------------------------------------- #
# Rectangular Ring Resonator
# ---------------------------------------------------------------------------- #

'''
This particular transfer function assumes that all four sides of the ring
resonator are straight and that the corners are rounded. Therefore, the
roundtrip length of the RR is 2*pi*radius + 2*couplerLength + 2*sideLength.

We assume that the round parts of the ring have negligble coupling compared to
the straight sections.

INPUTS:
wavelength .............. [np array](N,) wavelength points to evaluate
radius .................. [scalar] radius of the sides in microns
couplerLength ........... [scalar] length of the coupling region in microns
sideLength .............. [scalar] length of each side not coupling in microns
gap ..................... [scalar] gap in the coupler region in microns
width ................... [scalar] width of the waveguides in microns
thickness ............... [scalar] thickness of the waveguides in microns

OUTPUTS:
S ....................... [np array](N,4,4) Scattering matrix

'''
def rectangularRR(wavelength,radius=5,couplerLength=5,sideLength=5,
            gap=0.2,width=0.5,thickness=0.2):

    # Sanitize the input

    # Calculate transfer function output

    #
    return


# ---------------------------------------------------------------------------- #
# Loss and coupling extractor
# ---------------------------------------------------------------------------- #

from matplotlib import pyplot as plt

def extractor(power,wavelength):
    peakThreshold = 0.3
    distanceThreshold = 4e-3 / (wavelength[1]-wavelength[0])
    
    peaks, _ = find_peaks(1-power,height=peakThreshold,distance=distanceThreshold)
    results_half = peak_widths(1-power, peaks, rel_height=0.5)

    FWHM = results_half[0][0:-1] * (wavelength[1] - wavelength[0])
    FSR = np.diff(wavelength[peaks])

    F = FSR / FWHM
    E = 1 / (power[peaks[0:-1]])

    A = np.cos(np.pi/F) / (1 + np.sin(np.pi/F))
    B = 1 - 1/E * (1 - np.cos(np.pi/F))/(1 + np.cos(np.pi/F))

    a = np.sqrt(A/B) + np.sqrt(A/B - A)
    b = np.sqrt(A/B) - np.sqrt(A/B - A)

    w = wavelength[peaks[0:-1]]
    return a, b, w
