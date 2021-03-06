import simuPOP as sim

class Ne(sim.PyOperator):
    '''An operator that calculates the effective number of disease alleles
    at specified loci.
    '''
    def __init__(self, loci=sim.ALL_AVAIL, subPops=sim.ALL_AVAIL, vars=[],
            *args, **kwargs):
        self.loci = loci
        self.vars = vars
        self.subPops = subPops
        sim.PyOperator.__init__(self, func=self._Ne, *args, **kwargs)
    
    def _calcNe(self, freq):
        'Calculate Ne from allele frequencies'
        if len(freq) == 0 or freq[0] == 1:
            return 0
        else:
            f_dis = 1 - freq[0]
            return 1. / sum([(freq[x]/f_dis)**2 \
                for x in list(freq.keys()) if x != 0])
    
    def _Ne(self, pop):
        # calculate allele frequency
        sim.stat(pop, alleleFreq=self.loci, subPops=self.subPops, 
            vars=['alleleFreq_sp', 'alleleFreq'] if 'ne_sp' in self.vars else [])
        # determine loci 
        loci = range(pop.totNumLoci()) if self.loci == sim.ALL_AVAIL else self.loci
        # ne for the whole population
        if len(self.vars) == 0 or 'ne' in self.vars:
            pop.dvars().ne = {}
            for loc in loci:
                pop.dvars().ne[loc] = self._calcNe(pop.dvars().alleleFreq[loc])
        if 'ne_sp' in self.vars:
            if self.subPops == sim.ALL_AVAIL:
                subPops = range(pop.numSubPop())
            else:
                subPops = self.subPops
            for sp in subPops:
                pop.dvars(sp).ne = {}
                for loc in loci:
                    pop.dvars(sp).ne[loc]=self._calcNe(pop.dvars(sp).alleleFreq[loc])
        return True

def calcNe(pop, *args, **kwargs):
    'Calculate ne statistics of pop'
    Ne(*args, **kwargs).apply(pop)

