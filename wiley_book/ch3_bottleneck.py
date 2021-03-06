import simuPOP as sim
from simuPOP.plotter import VarPlotter
def demo(gen):
    # split subpopulation 0 at generation 10 and 20
    if gen >=40 and gen < 50:
        return 20
    else:
        return 1000

pop = sim.Population(size=1000, loci=1)
simu = sim.Simulator(pop, rep=5)
simu.evolve(
    initOps=[
        sim.InitSex(),
        sim.InitGenotype(freq=[0.5, 0.5])
    ],
    matingScheme=sim.RandomMating(subPopSize=demo),
    postOps=[
        sim.Stat(alleleFreq=0),
        VarPlotter('alleleFreq[0][0]', update=10,
            saveAs='Figures/bottleneck.pdf',
            plot_ylim=[0,1], plot_ylab='Allele Frequency',
            lines_col='black', lines_lwd=1.5)
    ],
    gen=101
)
