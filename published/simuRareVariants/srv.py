#!/usr/bin/env python
#
# Author: Bo Peng
#
# Purpose: Simulation of samples with rare variants.
#
'''
Simulating a population of sequences forward in time, subject to mutation,
natural selection and population expansion. Because most mutants are introduced
during the rapid population expansion, most of the alleles will be rare at the
end of the simulation. Samples simulated using this script can be used to study
genetic diseases caused by a large number of rare variants.
'''

#
# This script simulates mutants in mutational space. That is to say, mutants
# are stored as locations on chromosomes, instead of allele number. Because
# indiviudals have different number of mutants, zeros are used to fill the
# rest of the markers.
#

import simuOpt
import collections
simuOpt.setOptions(alleleType='long', optimized=True, quiet=True, version='1.0.5')

import simuPOP as sim
from simuPOP.utils import ProgressBar, migrIslandRates
from simuPOP import MutSpaceRevertFixedSites, revertFixedSites, MutSpaceSelector, MutSpaceMutator, MutSpaceRecombinator

import os, sys, logging, math, time

class NumSegregationSites(sim.PyOperator):
    '''A Python operator to count the number of segregation sites (number of
    distinct mutants), average number of segreagation sites of individuals,
    and average allele frequency of these mutants. The results are saved
    in variables ``numSites``, ``avgSites`` and ``avgFreq``.
    '''
    def __init__(self, *args, **kwargs):
        sim.PyOperator.__init__(self, func=self.countSites, *args, **kwargs)

    def countSites(self, pop):
        '''Count the number of segregation sites, average sites per individual,
        average allele frequency.'''
        revertFixedSites(pop)
        geno = pop.genotype()
        numMutants = float(len(geno) - geno.count(0)) 
        numSites = len(set(geno)) - 1
        if numMutants == 0:
            avgFreq = 0
        else:
            avgFreq = numMutants / numSites / (2*pop.popSize())
        pop.dvars().numSites = numSites
        pop.dvars().avgSites = float(numMutants) / pop.popSize()
        pop.dvars().avgFreq = avgFreq
        return True

def mutantsToAlleles(pop, logger):
    '''Convert a population from mutational space to allele space. Monomorphic
    markers are ignored.
    '''
    # figure out chromosomes and markers
    markers = {}
    for ch,region in enumerate(pop.chromNames()):
        chNumber = region.split(':')[0][3:]
        loci = set()
        for ind in pop.individuals():
            loci |= set(ind.genotype(0, ch))
            loci |= set(ind.genotype(1, ch))
        if chNumber in markers:
            markers[chNumber] |= loci
        else:
            markers[chNumber] = loci
    # create a population for each chromosome
    pops = []
    chroms = list(markers.keys())
    chroms.sort()
    for ch in chroms:
        markers[ch] = list(markers[ch])
        markers[ch].remove(0)
        markers[ch].sort()
        if logger:
            logger.info('Chromosome %s has %d markers' % (ch, len(markers[ch])))
        apop = sim.Population(pop.popSize(), loci=len(markers[ch]),
            lociPos=markers[ch])
        # get a dictionary of loci position
        lociPos = {}
        for idx,loc in enumerate(apop.lociPos()):
            lociPos[loc] = idx
        for aind,mind in zip(apop.individuals(), pop.individuals()):
            for p in range(2):
                for mutant in mind.genotype(p):
                    if mutant != 0:
                        aind.setAllele(1, lociPos[mutant], p)
        pops.append(apop)
    for pop in pops[1:]:
        pops[0].addChromFrom(pop)
    return pops[0]


def allelesToMutants(pop, regions, logger=None):
    '''Convert a population from allele space to mutational space, using
    specified regions.
    '''
    pops = []
    for region in regions:
        loci = []
        ch_name = region.split(':')[0][3:]
        start, end = [int(x) for x in region.split(':')[1].split('..')]
        try:
            ch = pop.chromByName(ch_name)
        except:
            raise ValueError('Chromosome %s is not available in passed population.' % ch_name)
        for loc in range(pop.chromBegin(ch), pop.chromEnd(ch)):
            pos = pop.locusPos(loc)
            if pos >= start and pos <= end:
                loci.append(loc)
        # get the mutants for each individual
        allAlleles = []
        for ind in pop.individuals():
            alleles0 = []
            alleles1 = []
            for loc in loci:
                if ind.allele(loc, 0) != 0:
                    alleles0.append(int(pop.locusPos(loc)))
                if ind.allele(loc, 1) != 0:
                    alleles1.append(int(pop.locusPos(loc)))
            allAlleles.extend([alleles0, alleles1])
        # maximum number of mutants
        maxMutants = max([len(x) for x in allAlleles])
        if logger is not None:
            logger.info('%d loci are identified with at most %d mutants in region %s.' % (len(loci), maxMutants, region))
        # create a population
        mpop = sim.Population(pop.popSize(), loci=maxMutants, chromNames=region)
        # put in mutants
        for idx,ind in enumerate(mpop.individuals()):
            geno = ind.genotype(0)
            for loc,mut in enumerate(allAlleles[idx*2]):
                geno[loc] = mut
            geno = ind.genotype(1)
            for loc,mut in enumerate(allAlleles[idx*2+1]):
                geno[loc] = mut
        pops.append(mpop)
    # merge all populations into one
    for pop in pops[1:]:
        pops[0].addChromFrom(pop)
    return pops[0]

def addMutantsFrom(pop, param):
    # Adding mutants
    extMutantFile, regions, logger = param
    mPop = sim.loadPopulation(extMutantFile)
    # convert allele-based population to mutation based population.
    mPop = allelesToMutants(mPop, regions, logger)
    #
    mPop.resize(pop.popSize())
    # Add loci to pop
    for ch in range(mPop.numChrom()):
        pop.addLoci([ch]*mPop.numLoci(ch), list(range(pop.numLoci(ch) + 1,
            pop.numLoci(ch) + mPop.numLoci(ch) + 1)))
    if logger:
        # if an initial population is given
        logger.info('Adding mutants to population after bottleneck')
    # Add mutants to pop
    for ind, mInd in zip(pop.individuals(), mPop.individuals()):
        for p in range(2):
            for ch in range(pop.numChrom()):
                geno = ind.genotype(p, ch)
                mGeno = mInd.genotype(p, ch)
                idx = geno.index(0)
                for i,m in enumerate(mGeno):
                    if m == 0:
                        break
                    geno[idx + i] = m
    return True


###
### The container.Counter class only exist in Python 2.7 so I put it here
###
from operator import itemgetter
from heapq import nlargest
from itertools import repeat

class Counter(dict):
    '''Dict subclass for counting hashable objects.  Sometimes called a bag
    or multiset.  Elements are stored as dictionary keys and their counts
    are stored as dictionary values.

    >>> Counter('zyzygy')
    Counter({'y': 3, 'z': 2, 'g': 1})

    '''

    def __init__(self, iterable=None, **kwds):
        '''Create a new, empty Counter object.  And if given, count elements
        from an input iterable.  Or, initialize the count from another mapping
        of elements to their counts.

        >>> c = Counter()                           # a new, empty counter
        >>> c = Counter('gallahad')                 # a new counter from an iterable
        >>> c = Counter({'a': 4, 'b': 2})           # a new counter from a mapping
        >>> c = Counter(a=4, b=2)                   # a new counter from keyword args

        '''        
        self.update(iterable, **kwds)

    def __missing__(self, key):
        return 0


    def elements(self):
        '''Iterator over elements repeating each as many times as its count.

        >>> c = Counter('ABCABC')
        >>> sorted(c.elements())
        ['A', 'A', 'B', 'B', 'C', 'C']

        If an element's count has been set to zero or is a negative number,
        elements() will ignore it.

        '''
        for elem, count in self.items():
            for _ in repeat(None, count):
                yield elem

    # Override dict methods where the meaning changes for Counter objects.

    @classmethod
    def fromkeys(cls, iterable, v=None):
        raise NotImplementedError(
            'Counter.fromkeys() is undefined.  Use Counter(iterable) instead.')

    def update(self, iterable=None, **kwds):
        '''Like dict.update() but add counts instead of replacing them.

        Source can be an iterable, a dictionary, or another Counter instance.

        >>> c = Counter('which')
        >>> c.update('witch')           # add elements from another iterable
        >>> d = Counter('watch')
        >>> c.update(d)                 # add elements from another counter
        >>> c['h']                      # four 'h' in which, witch, and watch
        4

        '''        
        if iterable is not None:
            if hasattr(iterable, 'iteritems'):
                if self:
                    self_get = self.get
                    for elem, count in iterable.items():
                        self[elem] = self_get(elem, 0) + count
                else:
                    dict.update(self, iterable) # fast path when counter is empty
            else:
                self_get = self.get
                for elem in iterable:
                    self[elem] = self_get(elem, 0) + 1
        if kwds:
            self.update(kwds)

    def __delitem__(self, elem):
        'Like dict.__delitem__() but does not raise KeyError for missing values.'
        if elem in self:
            dict.__delitem__(self, elem)

    def __repr__(self):
        if not self:
            return '%s()' % self.__class__.__name__
        items = ', '.join(map('%r: %r'.__mod__, self.most_common()))
        return '%s({%s})' % (self.__class__.__name__, items)
 
#
# End of copied code
#


def saveMarkerInfoToFile(pop, filename, logger=None):
    '''Save a map file with an additional column of allele frequency. The
    population has to be in mutational space. This function assumes that
    there is a variable selCoef in this population which contains selection
    coefficients for all mutants.
    '''
    allCounts = [Counter() for x in range(pop.numChrom())]
    prog = ProgressBar('Counting number of mutants', pop.popSize())
    for ind in pop.individuals():
        # there can be memory problem....
        for ch in range(pop.numChrom()):
            allCounts[ch].update(ind.genotype(0, ch))
            allCounts[ch].update(ind.genotype(1, ch))
        prog.update()
    allMutants = []
    selCoef = pop.dvars().selCoef
    if filename:
        map = open(filename, 'w')
        print('name\tchrom\tposition\tfrequency\ts\th', file=map)
    for ch,region in enumerate(pop.chromNames()):
        # real chromosome number
        chName = region.split(':')[0][3:]
        counts = allCounts[ch]
        # get markers
        mutants = list(counts.keys())
        mutants.sort()
        # allele 0 is fake
        if mutants[0] == 0:
            mutants = mutants[1:]
        allMutants.append(mutants)
        if filename:
            # find all markers
            sz = pop.popSize() * 2.
            for idx,marker in enumerate(mutants):
                if type(selCoef) == type({}):
                    print('loc%d_%d\t%s\t%d\t%.8f\t%.8f\t%.3f' % (ch + 1, idx + 1, chName, marker,
                        counts[marker] / sz, selCoef[marker][0], selCoef[marker][1]), file=map)
                else:
                    print('loc%d_%d\t%s\t%d\t%.8f\t%.8f\t%.3f' % (ch + 1, idx + 1, chName, marker,
                        counts[marker] / sz, selCoef, 0.5), file=map)
    if filename:
        map.close()
    return allMutants
        

def saveMutantsToFile(pop, filename, infoFields=[], logger=None):
    '''Save haplotypes as a list of mutant locations to file, in the format of
       ind_idx reg_id FIELDS mut1 mut2 ...
    where FIELDS are information fields.
    '''
    mut = open(filename, 'w')
    prog = ProgressBar('Writing mutants of %d individuals to %s' % (pop.popSize(), filename), pop.popSize())
    for idx,ind in enumerate(pop.allIndividuals()):
        fields = ' '.join([str(ind.info(x)) for x in infoFields])
        for ch in range(pop.numChrom()):
            geno = list(ind.genotype(0, ch))
            geno.sort()
            print(idx+1, fields, ' '.join([str(x) for x in geno if x != 0]), file=mut)
            geno = list(ind.genotype(1, ch))
            geno.sort()
            if geno[0] == 0:
                geno = geno[1:]
            print(idx+1, fields, ' '.join([str(x) for x in geno if x != 0]), file=mut)
        prog.update()
    mut.close()

def saveGenotypeToFile(pop, filename, allMutants, logger=None):
    '''Save genotype in .ped file format. Because there is no family structure, we have
        famid = 1, 2, 3, ...
        id = 1
        fa = 0
        ma = 0
        sex = 1 for male and 2 for female
        aff = 1 for unaffected and 2 for affected
        genotype 

    allMutants:
        lists of mutants returned by function markerFile
    '''
    if logger:
        logger.info('Saving genotype to %s in standard .ped format.' % filename)
    ped = open(filename, 'w')
    # marker index...
    markerPos = []
    for mutants in allMutants:
        pos = {}
        for idx,m in enumerate(mutants):
            pos[m] = idx
        markerPos.append(pos)
    prog = ProgressBar('Writing genotype of %d individuals to %s' % (pop.popSize(), filename), pop.popSize())
    sexCode = {sim.MALE: 1, sim.FEMALE: 2}
    affCode = {False: 1, True: 2}
    for cnt, ind in enumerate(pop.individuals()):
        print('%s 0 0 %d %d' % (cnt + 1, sexCode[ind.sex()], affCode[ind.affected()]), end=' ', file=ped)
        for ch in range(pop.numChrom()):
            # a blank genotype
            geno = [0]*(len(markerPos[ch])*2)
            # add 1 according to mutant location (first ploidy)
            for m in ind.genotype(0, ch):
                if m == 0:
                    break
                geno[2*markerPos[ch][m]] = 1
            # add 1 according to mutant location (second ploidy)
            for m in ind.genotype(1, ch):
                if m == 0:
                    break
                geno[2*markerPos[ch][m]+1] = 1
            print(' '.join([str(x) for x in geno]), end=' ', file=ped)
        print(file=ped)
        prog.update()
    ped.close()

class fitnessCollector:
    '''This is a simple connection class that gets output from 
    a InfSiteSelector and collect mutant fitness'''
    def __init__(self):
        self.selCoef = {}

    def getCoef(self, lines):
        for line in lines.strip().split('\n'):
            mut, sel, h = line.split()
            self.selCoef[int(mut)] = float(sel), float(h)


def mixedGamma(selCoef):
    '''This function returns a random fitness value for a new mutant
    according to a mixed_gamma distribution. If a parameter loc is defined,
    locus index will be passed so that you can return different selection
    coefficient for different locations.
    '''
    # selCoef: (p, a, k, theta, h)
    if len(selCoef) == 5:
        selCoef = list(selCoef) + [0.0001, 0.1]
    if len(selCoef) != 7:
        raise ValueError("A list of five or seven parameters is needed.")
    def func():
        if sim.getRNG().randUniform() < selCoef[0]:
            return selCoef[1], selCoef[4]
        while True:
            s = sim.getRNG().randGamma(selCoef[2], selCoef[3])
            if s > selCoef[5] and s < selCoef[6]:
                return s, selCoef[4]
    return func

def mixedGamma1(selCoef):
    '''This function returns a random fitness value for a new mutant
    according to a mixed_gamma distribution. If a parameter loc is defined,
    locus index will be passed so that you can return different selection
    coefficient for different locations.
    '''
    # selCoef: (p, a, k, theta, h, l, u)
    if len(selCoef) != 7:
        raise ValueError("A list of seven parameters is needed.")
    def func():
        if sim.getRNG().randUniform() < selCoef[0]:
            return selCoef[1], selCoef[4]
        while True:
            s = sim.getRNG().randGamma(selCoef[2], selCoef[3])
            if s >= selCoef[5] and s <= selCoef[6]:
                return s, selCoef[4]
            elif s < selCoef[5]:
                return 0.0, selCoef[4]
            elif s > selCoef[6]:
                return 1.0, selCoef[4]
    return func

def multiStageDemoFunc(N, G, splitTo, splitAt):
    '''Return a demographic function with specified parameter
    '''
    # the demographic model: N[0] = the population size of the burnin generation
    # 0,    G[0], G[0] + G[1], ..., reflexting
    # N[0], N[1], N[2], ....
    Gens = [sum(G[:i]) for i in range(len(G)+1)]
    #
    def demoFunc(gen, pop):
        if len(splitTo) > 1 and gen == splitAt:
            pop.splitSubPop(0, splitTo)
        nSP = pop.numSubPop()
        # default
        sz = N[-1]
        for i in range(len(G)):
            if Gens[i] <= gen < Gens[i+1]:
                # at constant or any bottleneck stage
                if N[i] >= N[i+1]:
                    sz = N[i+1]
                # at any expansion stage
                else:
                    # to make sure that the last generation of this expansion stage 
                    # has the exact required number of individuals.
                    if gen == Gens[i+1] - 1:
                        sz = N[i+1]
                    else:
                        r = math.log(N[i+1] * 1.0 / N[i]) / G[i]
                        sz = int(N[i] * math.exp(r*(gen - Gens[i])))
                break
        # because population might be split, ..
        if nSP == 1:
            return sz
        else:
            # split with proportion
            sz1 = [int(sz*x) for x in splitTo]
            # remenders are given to the last subpopulation
            sz1[-1] += sz - sum(sz1)
            return sz1
    return demoFunc

def simuRareVariants(regions, N, G, mu, selDist, selCoef, selModel='exponential', recRate=0, 
        splitTo=[1], splitAt=0, migrRate=0, steps=[100], mutationModel='finite_sites',
        initPop='', extMutantFile='', addMutantsAt=0, postHook=None,
        statFile='', popFile='', markerFile='', mutantFile='', genotypeFile='',
        verbose=1, logger=None):
    '''
    Please refer to simuRareVariants.py -h for a detailed description of all parameters.
    Note that a user-defined function can be passed to parameter selDist to specify
    arbitrary distribution of fitness. A script-only feature is that a Python function
    can be provided through parameter postHook to process the population at each generation.
    '''
    #
    # convert regions to start/end positions
    ranges = []
    chromTypes = []
    for region in regions:
        start, end = [int(x) for x in region.split(':')[1].split('..')]
        ranges.append((start, end+1))
        if region.split(':')[0] == 'chrX':
            chromTypes.append(sim.CHROMOSOME_X)
            if len(regions) > 1:
                raise ValueError('The current implementation only allows one region if it is on chromosome X')
            logger.info('Chromosome {} is on chromosome X'.format(region))
        elif region.split(':')[0] == 'chrY':
            raise ValueError('The current implementation does not support chromosome Y')
            chromTypes.append(sim.CHROMOSOME_Y)
            logger.info('Chromosome {} is on chromosome Y'.format(region))
        else:
            chromTypes.append(sim.AUTOSOME)
    if logger:
        logger.info('%s regions with a total length of %d basepair.' % (len(ranges), sum([x[1]-x[0] for x in ranges])))
    #
    # set default parameter
    if selCoef is None:
        # set default parameters
        if selDist == 'mixed_gamma':
            selCoef = [0.0186, 0.0001, 0.184, 0.160*2, 0.5, 0.0001, 0.1]
        elif selDist == 'mixed_gamma1':
            selCoef = [0, -1, 0.562341, 0.01, 0.5, 0.00001, 0.1]
        elif selDist == 'gamma1':
            selCoef = [0.23, 0.185*2, 0.5]
        elif selDist == 'gamma2':
            selCoef = [0.184, 0.160*2, 0.5]
        elif selDist == 'gamma3':
            selCoef = [0.206, 0.146*2, 0.5]
        elif selDist == 'constant':
            selCoef = [0.01, 0.5]
        elif not isinstance(selDist, collections.Callable):
            raise ValueError("Unsupported random distribution")
    else:
        # force to list type
        selCoef = list(selCoef)
    if len(steps) == 0:
        # at the end of each stage
        steps = G
    elif len(steps) == 1:
        # save step for each stage
        steps = steps * len(G)
    # use a right selection operator.
    collector = fitnessCollector()
    mode = {'multiplicative': sim.MULTIPLICATIVE,
        'additive': sim.ADDITIVE,
        'exponential': sim.EXPONENTIAL}[selModel]
    #
    if type(popFile) == str:
        popFile = [popFile, -1]
    #
    if isinstance(selDist, collections.Callable):
        mySelector = MutSpaceSelector(selDist=selDist, mode=mode, output=collector.getCoef)
    elif selDist == 'mixed_gamma':
        mySelector = MutSpaceSelector(selDist=mixedGamma(selCoef), mode=mode, output=collector.getCoef)
    elif selDist == 'mixed_gamma1':
        mySelector = MutSpaceSelector(selDist=mixedGamma1(selCoef), mode=mode, output=collector.getCoef)
    elif selDist.startswith('gamma'):
        mySelector = MutSpaceSelector(selDist=[sim.GAMMA_DISTRIBUTION]+selCoef,
            mode=mode, output=collector.getCoef)
    elif selDist == 'constant':
        if selCoef == 0:
            mySelector = sim.NoneOp()
        else:
            mySelector = MutSpaceSelector(selDist=[sim.CONSTANT] + selCoef,
                mode=mode, output=collector.getCoef)
    #
    # Evolve
    if os.path.isfile(initPop):
        if logger:
            logger.info('Loading initial population %s...' % initPop)
        pop = sim.loadPopulation(initPop)
        if pop.numChrom() != len(regions):
            raise ValueError('Initial population %s does not have specified regions.' % initPop)
        for ch,reg in enumerate(regions):
            if pop.chromName(ch) != reg:
                raise ValueError('Initial population %s does not have region %s' % (initPop, reg))
        pop.addInfoFields(['fitness', 'migrate_to'])
    else:
        pop = sim.Population(size=N[0], loci=[10]*len(regions), chromNames=regions,
            infoFields=['fitness', 'migrate_to'], chromTypes=chromTypes)
    if logger:
        startTime = time.clock()
    #
    progGen = []
    # 0, G[0], G[0]+G[1], ..., sum(G)
    Gens = [sum(G[:i]) for i in range(len(G)+1)]
    for i in range(len(Gens)-1):
        progGen += list(range(Gens[i], Gens[i+1], steps[i]))
    pop.evolve(
        initOps=sim.InitSex(),
        preOps=[
            sim.PyOutput('''Statistics outputted are
1. Generation number,
2. population size (a list),
3. number of segregation sites,
4. average number of segregation sites per individual
5. average allele frequency * 100
6. average fitness value
7. minimal fitness value of the parental population
''', at = 0)] + \
            [sim.PyOutput('Starting stage %d\n' % i, at = Gens[i]) for i in range(0, len(Gens))] + \
            # add alleles from an existing population 
            [sim.IfElse(extMutantFile != '',
                ifOps = [
                    sim.PyOutput('Loading and converting population %s' % extMutantFile),
                    sim.PyOperator(func=addMutantsFrom, param=(extMutantFile, regions, logger)),
                ], at = addMutantsAt),
            # revert alleles at fixed loci to wildtype
            MutSpaceRevertFixedSites(),
            # mutate in a region at rate mu, if verbose > 2, save mutation events to a file
            MutSpaceMutator(mu, ranges, {'finite_sites':1, 'infinite_sites':2}[mutationModel],
                output='' if verbose < 2 else '>>mutations.lst'),
            # selection on all loci
            mySelector,
            # output statistics in verbose mode
            sim.IfElse(verbose > 0, ifOps=[
                sim.Stat(popSize=True, meanOfInfo='fitness', minOfInfo='fitness'),
                NumSegregationSites(),
                sim.PyEval(r'"%5d %s %5d %.6f %.6f %.6f %.6f\n" '
                    '% (gen, subPopSize, numSites, avgSites, avgFreq*100, meanOfInfo["fitness"], minOfInfo["fitness"])',
                    output='>>' + statFile),
                ], at = progGen
            ),
            sim.IfElse(len(splitTo) > 1,
                sim.Migrator(rate=migrIslandRates(migrRate, len(splitTo)),
                    begin=splitAt + 1)
            ),
        ],
        matingScheme=sim.RandomMating(ops=MutSpaceRecombinator(recRate, ranges),
            subPopSize=multiStageDemoFunc(N, G, splitTo, splitAt)),
        postOps = [
            sim.NoneOp() if postHook is None else sim.PyOperator(func=postHook),
            sim.SavePopulation(popFile[0], at=popFile[1]),
        ],
        finalOps=[
            # revert fixed sites so that the final population does not have fixed sites
            MutSpaceRevertFixedSites(),
            sim.IfElse(verbose > 0, ifOps=[
                # statistics after evolution
                sim.Stat(popSize=True),
                NumSegregationSites(),
                sim.PyEval(r'"%5d %s %5d %.6f %.6f %.6f %.6f\n" '
                    '% (gen+1, subPopSize, numSites, avgSites, avgFreq*100, meanOfInfo["fitness"], minOfInfo["fitness"])',
                    output='>>' + statFile),
                sim.PyEval(r'"Simulated population has %d individuals, %d segregation sites.'
                           r'There are on average %.1f sites per individual. Mean allele frequency is %.4f%%.\n"'
                           r'% (popSize, numSites, avgSites, avgFreq*100)'),
            ]),
        ],
        gen = Gens[-1]
    )
    # record selection coefficients to population
    if len(collector.selCoef) == 0:
        # this must be the neutral case where a NonOp has been used.
        pop.dvars().selCoef = 0
    else:
        pop.dvars().selCoef = collector.selCoef
    # re-save the file with the added selCoef
    if popFile[-1] == -1:
        pop.save(popFile[0])
    #
    if logger:
        logger.info('Population simulation takes %.2f seconds' % (time.clock() - startTime))
    if markerFile or genotypeFile:
        if logger:
            logger.info('Saving marker information to file %s' % markerFile)
        mutants = saveMarkerInfoToFile(pop, markerFile, logger)
        if genotypeFile:
            if logger:
                logger.info('Saving genotype in .ped format to file %s' % genotypeFile)
            saveGenotypeToFile(pop, genotypeFile, mutants, logger)
    if mutantFile:
        if logger:
            logger.info('Saving mutants to file %s' % mutantFile)
        saveMutantsToFile(pop, mutantFile, logger=logger)
    return pop


if __name__ == '__main__':
    import argparse
    args = argparse.ArgumentParser(description='A simulator of rare variants.')
    args.add_argument("--regions",
        default=['chr1:1..50000'],
        nargs="*",
        help="""Regions
            A region (in basepair) means a piece of chromosome in
            which mutations can happen. A region should be expressed as chrXX:YYYY..ZZZZ
            where XX is chromosome number, YYYY is the starting position in basepair and
            ZZZZ is the ending position in basepair. The starting position should be at
            least one. If multiple regions are specified as a list of regions, they
            are assumed to be unlinked and will segregate independently even if they are
            on the same chromosome. If chromosome is 'chrX' or 'chrY', they will be
            transmitted as sex chromosomes. The current implementation only allows
            one region on a sex chromosome.""")
    args.add_argument("--initPop",
        default='',
        help="""Initial population
            Name of an initial population. If this file exists, it
            will be loaded and the evolution will start from this population, instead
            of a blank population.
         """)
    args.add_argument("--N",
        default=[8100, 8100, 7900, 900000],
        nargs='*',
        help="""Population Sizes
            Assuming a n stage demographic model, this parameter specifies
            population sizes at the beginning of evolution and at the end of each stage.
            N_0,...,N_n. If N_i < N_i+1, an exponential population expansion model will be
            used to expand population from size N_i to N_i+1. If N_i < N_i+1, an instant
            population reduction will reduce population size to N_i+1. For example
            | N=(1000,1000,100,1000)
            |simulates a three stage demographic model where a population of constant size
            goes through a bottleneck of 100 indiviudals, and then expands exponentially to
            a size of 1000.""")
    args.add_argument("--G",
        default=[5000, 10, 370],
        nargs='*',
        help="""Numbers of generations at each stage
            Numbers of generations of each stage of a n stage demographic model.
            This parameter should have n elements, in comparison to n+1 elements for parameter
            N.""")
    args.add_argument("--splitTo",
        default=[1],
        type=float,
        nargs='*',
        help="""Proportions of subpopulation sizes
            This parameter, if specified, should be a list of proportions that
            add up to 1. The length of this list specifies the number of subpopulations to
            split.""")
    args.add_argument("--splitAt",
        default=0,
        type=int,
        help="""Split population at generation
            Split the population at specified generation according to specified
            proportions.""")
    args.add_argument("--mutationModel",
        default='finite_sites',
        nargs="*",
        help="""Mutation model
            Mutation model. The default mutation model is a finite-site
            model that allows mutations at any locus. If a mutant is mutated, it will be
            mutated to a wildtype allele. Alternatively, an infinite-sites model can be
            simulated where new mutants must happen at loci without existing mutant,
            unless no vacant loci is available (a warning message will be printed 
            in that case).""")
    args.add_argument("--mu",
        default=1.8e-08,
        type=float,
        nargs='*',
        help="""Mutation rate
            Mutation rate""")
    args.add_argument("--selModel",
        default='multiplicative',
        nargs="*",
        help="""Multi-locus selection model
            Multi-locus selection model, namely how to obtain an
            overall individual fitness after obtaining fitness values at all loci.
            This script supports three models:
            |  multiplicative: prod (f_i) Product of individual fitness.
            |  additive: max(0, 1 - sum(1-f_i)) One minus the combined selection 
                deficiencies.
            |  exponential: exp(sum(1-f_i)) Exponential of combined selection
                deficiencies.
            |Note that f_i can be equal to or greater than zero, which represents
            neutral loci, or loci under positive selection.""")
    args.add_argument("--selDist",
        default='constant',
        help="""Distribution of selection coefficient
            Distribution of selection coefficient for new mutants.
            Each distribution specifies s (selection coefficient) and h (dominance
            coefficient, default to 0.5 for additivity) that assign fitness values
            1, 1-hs and 1-s for genotypes AA (wildtype), Aa and aa, respectively.
            Note that positive s is used for negative selection so negative s is
            needed to specify positive selection. Note that we use 2k in the default
            distribution of Gamma distributions because theoretical estimates of 
            s is for each mutant with 1-2s as fitness value for genotype aa in
            our model. This script currently support the following distributions:
            |* constant: A single selection coefficient that gives each mutant a
                constant value s. The default parameter for this model is 
                0.01, 0.5. You can set selCoef to 0 to simulate neutral cases or a
                negative value for positive selection.
            |* gamma1: A basic gamma distribution assuming a constant
                population size model (Eyre-Walker et al, 2006). The default
                parameters for this model is Pr(s=x)=Gamma(0.23, 0.185*2), with h=0.5.
                A scaling parameter 0.185*2 is used because s in our simulation
                accounts for 2s for Eyre-Walker et al.
            |* gamma2: A gamma distribution assuming a two-epoch population
                size change model for African population (Boyko et al, 2008). The
                default parameters for this model is Pr(s=x)=Gamma(0.184, 0.160*2),
                with h=0.5.
            |* gamma3: A gamma distribution (for s) assuming a complex bottleneck
                model for European population (Boyko et al, 2008). The default
                parameters for this model is Pr(s=x)=Gamma(0.206, 0.146*2) with h=0.5.
            |* mixed_gamma: Parameter of this model should be a list of
                (a, p, k, theta, h, l, u) where a is the probability of having s=p (neutral
                or adptive sites), k, theta are the parameter of a gamma distribution
                Recomended parameter is (0.0186, 0.0001, 0.184, 0.160*2, 0.5, 0.0001, 0.1) for
                P(s=0.0001)=0.0186 and P(s=x)=(1-0.0186)*Gamma(0.184,0.160*2), with values
                outside of (l,u) being discarded.
            |* mixed_gamma1: A gamma distribution assuming a single bottleneck followed by
                exponential expansion for European population (Kyrukov et al, 2009). 
                The default parameters for this model is Pr(s=x)=Gamma(0.562341, 0.01)
                with h=0.5. Tails of this distribution (above s=0.1 and below s=0.00001)
                have being replaced by s=1 and s=0 respectively. If you would like to 
                reset some of the parameters, you can set (a, p, k, theta, h, l, u)
                to parameter selCoef where a is the probability of having selection 
                coefficient = p (usually p = 0 for neutral or < 0 for protective), 
                l/u are lower/upper bounds for selection coefficients, creating truncated 
                gamma distribution. k, theta are the parameters of the gamma distribution.
            |If you would like to define your own selection model, please define
            your own function and pass it to parameter selDist of function
            simuRareVariants in the script.""")
    args.add_argument("--selCoef",
        default=None,
        nargs="*",
        help="""Customized selection coefficient
            Selection coefficient with its meaning determined by
            parameter selDist. If None is given, the default parameter for the
            selected distribution will be used. For example, parameter (0.001, 0)
            for a constant model defines a recessive model with fixed s. Note that
            a parameter of (k, theta, h) is needed for gamma distributions and
            a parameter of (p, a, k, theta, h, l, v) is needed for mixed gamma
            distributions.""")
    args.add_argument("--recRate",
        default=0,
        type=float,
        help="""Recombination rate
            Recombination rate per base pair. If r times loci distance
            if greater than 0.5, a rate of 0.5 will be used.""")
    args.add_argument("--migrRate",
        default=0,
        type=float,
        help="""Migration rate
            Migration rate to migrate individuals between subpoulations
            after the population is split into several subpopulations. An island model
            is used.""")
    args.add_argument("--extMutantFile",
        default='',
        help="""Add mutants from population
            If a population is given, mutants from this population
            will be added to the population at specified generation. Only
            loci that are within the specified regions will be inserted. This
            population will be resized to population size at addMutantsAt
            before it is merged to the simulated population. This population is
            usually prepared using selectMarkers.py, using HapMap populations loaded
            using scripts loadHapMap2.py and loadHapMap3.py. These scripts are
            available from the simuPOP cookbook.""")
    args.add_argument("--addMutantsAt",
        default=0,
        type=int,
        help="""Add mutants at generation
            Generation number at which mutants from an external
            population will be inserted to the evolving population.""")
    args.add_argument("--steps",
        default=[100],
        nargs='*',
        help="""Frequency of statistic output
            Calculate and output statistics at intervals of specified
            number of generations. A single number or a list of numbers for each stage
            can be specified. If left unspecified, statistics at the beginning of
            each stage will be printed.""")
    args.add_argument("--statFile",
        default='',
        type=str,
        help="""Output statistics to
            File to output statistics. Default to standard output.""")
    args.add_argument("--popFile",
        default='output.pop',
        type=str,
        help="""Save population during evolution
            Filename to which the evolving population will be saved
            in simuPOP format. The default value of this parameter is 'output.pop',
            which saves the population at the end of the evolution to file 'output.pop'.
            Optionally, one or more generation numbers can be provided,
            in which case, the filename should be specified as an expression. For
            example, parameter ('!"output_%d.pop" % gen', (5000, -1)) saves the
            evolving population at the end of generation 5000, and the last generation.
            Please check the simuPOP user's guide for the use of expression in 
            operator savePopulation.""")
    args.add_argument("--markerFile",
        default='output.map',
        type=str,
        help="""Save marker information to
            Filename to which the marker information, including
            marker name (reg+index), chromosome, location, allele frequency and
            selection coefficient are saved. Monomorphic markers are ignored.""")
    args.add_argument("--mutantFile",
        default='output.mut',
        type=str,
        help="""Save mutants to
            Filename to which the mutants are outputed. The file
            will be saved in the format of 
            |  ind_id mut1 mut2 ...
            |where ind_id is the index of individual (1, 2, ...), mut1 and mut2 are
            locations of mutants. Haplotypes for different regions and homologous
            chromosomes are saved in different lines in the order of 
            | reg1_ploidy1
            | reg1_ploidy2
            | reg2_ploidy1
            | reg2_ploidy2
            | ...
            """)
    args.add_argument("--genotypeFile",
        default='',
        type=str,
        help="""Save genotype (in .ped format) to
            Filename to which the genotypes of all individuals are
            saved. The file will be saved in the format of
            |    famid id fa mo sex aff loc1_a1 loc1_a2 loc2_a1 loc2_a2 ...
            |where famid is 1, 2, 3, ... id is always 1, fa, mo is always 0.
            Wildtype and mutant alleles are denoted by 0 and 1 respectively. This
            option is turned off by default because this format is not efficient in
            storing a small number of mutants.""")
    args.add_argument("--verbose",
        default=1,
        type=int,
        help="""
            0 for quiet, 1 for regular output, 2 for debug output.
            In the debug output, a file 'mutations.lst' will be saved with all 
            mutation events. This option is not visible from gui.""")
    args = args.parse_args()

    # if you change level to logging.DEBUG, a lot of debug information, including
    # location and generation of mutants will be outputed. You can also use parameter
    # filename of function basicConfig to output log to a file.
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('simuRareVariants')
    simuRareVariants(logger=logger, **vars(args))


