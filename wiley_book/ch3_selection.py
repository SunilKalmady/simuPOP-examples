import simuPOP as sim
from simuPOP.plotter import VarPlotter
pop = sim.Population(size=10000, loci=1, infoFields='fitness')
simu = sim.Simulator(pop, rep=3)
h = [0.5, 0.2, -0.5]
s = [0.1, -0.1, 0.1]
simu.evolve(
    initOps=[
        sim.InitSex(),
        sim.InitGenotype(freq=(0.5, 0.5))
    ],
    preOps=[sim.MapSelector(loci=0,
        fitness={(0,0):1, (0,1):1-h[x]*s[x], (1,1):1-s[x]}, reps=x)
        for x in range(3)],
    matingScheme=sim.RandomMating(),
    postOps=[
        sim.Stat(alleleFreq=0),
        sim.PyEval(r'"%.3f\t" % alleleFreq[0][1]', step=50),
        sim.PyOutput('\n', reps=-1, step=50),
        VarPlotter('alleleFreq[0][0]', update=200,
            legend=['h=%.1f s=%.1f' % (x,y) for x,y in zip(h,s)],
            saveAs='Figures/selection.pdf',
            lines_lty_rep=[1, 2, 3], lines_col='black',
            lines_lwd=2, legend_x=120, legend_y=0.3,
            plot_ylab='Allele Frequency', plot_ylim=[0,1]),
    ],
    gen=201
)
