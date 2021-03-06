#!/usr/bin/env python
#
# Demonstrate the decay of linkage disequilibrium
#
# Author: Bo Peng (bpeng@mdanderson.org)
#

"""
This program demonstrate the decay of linkage disequilibrium due
to recombination.
"""

import simuOpt, os, sys, types, time
from simuPOP import *

try:
    from simuPOP.plotter import *
except:
    print "simuRPy import failed. Please check your rpy installation."
    print "LD values will not be plotted"
    useRPy = False
else:
    useRPy = True

options = [
    {'name':'size',
     'default':1000,
     'label':'Population Size',
     'type':[int, long],
     'validator':simuOpt.valueGT(0),
    },
    {'name':'gen',
     'default':50,
     'type':[int, long],
     'label':'Generations to evolve',
     'description':'Length of evolution',
     'validator':simuOpt.valueGT(0)
    },
    {'name':'recRate',
     'default':0.01,
     'label':'Recombination Rate',
     'type':[float],
     'validator':simuOpt.valueBetween(0.,1.),
    },
    {'name':'numRep',
     'default':5,
     'label':'Number of Replicate',
     'type':[int, long],
     'description':'Number of replicates',
     'validator':simuOpt.valueGT(0)
    },
    {'name':'measure',
     'default':'D',
     'label':'LD measure',
     'description':'Choose linkage disequilibrium measure to be outputted.',
     'chooseOneOf':['D', "D'", 'R2'],
     'validator': simuOpt.valueOneOf(['D', "D'", 'R2']),
    },
    {'name':'saveFigure',
     'label':'Save figure to filename',
     'default':'',
     'type':[str],
     'description': '''If specified, save the figures to files such as filename_10.eps.
        The format the figures is determined by file extension.
        '''
    },
    {'name':'save',
     'default':'',
     'type':[str],
     'description':'Save current paremeter set to specified file.'
    },
]


def simuLDDecay(popSize, gen, recRate, numRep, method, saveFigure, useRPy):
    '''Simulate the decay of linkage disequilibrium as a result
    of recombination.
    '''
    # diploid population, one chromosome with 2 loci
    # random mating with sex
    simu = Simulator(
        Population(size=popSize, ploidy=2, loci=[2]),
        rep = numRep)

    # get method value used to plot and evolve
    if method=="D'":
        methodplot = "LD_prime[0][1]"
        upperlim = 1
        methodeval = r"'%.4f\t' % LD_prime[0][1]"
    elif method=='R2':
        methodplot = "R2[0][1]"
        upperlim = 1
        methodeval = r"'%.4f\t' % R2[0][1]"
    else:
        methodplot = "LD[0][1]"
        upperlim = 0.25
        methodeval = r"'%.4f\t' % LD[0][1]"

    if useRPy:
        print saveFigure
        plotter = VarPlotter(methodplot, 
            ylim = [0, upperlim], saveAs=saveFigure,
            update = gen - 1, ylab=method, leaveOpen=True,
            main="Decay of Linkage Disequilibrium r=%f" % recRate)
    else:
        plotter = NoneOp()

    simu.evolve(
        # everyone will have the same genotype: 01/10
        initOps = [
            InitSex(),
            InitGenotype(genotype=[0,1,1,0])
        ],
        matingScheme = RandomMating(ops=Recombinator(rates = recRate)), 
        postOps = [
            Stat(alleleFreq=[0], LD=[0, 1]),
            PyEval(methodeval),
            PyOutput('\n', reps=-1),
            plotter
        ],
        gen = gen
    )


if __name__ == '__main__':
    # get all parameters
    pars = simuOpt.Params(options, __doc__)
    # cancelled or -h, --help
    if not pars.getParam():
        sys.exit(0)

    if pars.save != '':
        pars.saveConfig(pars.save)

    simuLDDecay(pars.size, pars.gen, pars.recRate, pars.numRep,
        pars.measure, pars.saveFigure, useRPy)

    # wait five seconds before exit
    if useRPy:
        print "Figure will be closed after five seconds."
        time.sleep(5)

