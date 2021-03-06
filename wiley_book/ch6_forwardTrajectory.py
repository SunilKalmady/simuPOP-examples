import math
from simuPOP.utils import *
# case 1: constant population size
traj = simulateForwardTrajectory(N=4000, fitness=[1, 0.999, 0.998],
    beginGen=0, endGen=500, beginFreq=0.2, endFreq=[0.1, 0.11])
# case 2: exponential population expansion
def Nt(gen):
    return int(4000*math.exp(gen*0.01))

traj = simulateForwardTrajectory(N=Nt, fitness=[1, 0.999, 0.998],
    beginGen=0, endGen=500, beginFreq=0.2, endFreq=[0.1, 0.11])
# case 3: balancing selection
traj = simulateForwardTrajectory(N=4000, fitness=[1, 1.001, 0.998],
    beginGen=0, endGen=500, beginFreq=0.2, endFreq=[0.2, 0.22])
# case 4: varying selection pressure
def fitnessFunc(gen, subPop):
    if gen > 200:
        return (1, 0.996, 0.994)
    else:
        return (1, 1, 1.02)

traj = simulateForwardTrajectory(N=4000, fitness=fitnessFunc,
    beginGen=0, endGen=500, beginFreq=0.2, endFreq=[0.15, 0.16])
