import os,glob,shutil

from openmdao.main.api import Component, Assembly, FileMetadata
from openmdao.lib.components.external_code import ExternalCode
from openmdao.main.datatypes.slot import Slot
from openmdao.main.datatypes.api import Array, Float

from AeroelasticSE.runFAST import runFAST
from AeroelasticSE.runTurbSim import runTurbSim
from AeroelasticSE.mkgeom import makeGeometry

from runCase import RunCase, FASTRunCaseBuilder, FASTRunCase, RunResult, FASTRunResult

########### aerocode #####################
## generic aeroelastic analysis code (e.g. FAST, HAWC2,)
#class openAeroCode(Component):
class openAeroCode(Assembly):
    """ base class for application that can run a DesignLoadCase """

    ## inputs and outputs are very generic:
    input = Slot(RunCase, iotype='in')
    output = Slot(RunResult, iotype='out')  ## never used, never even set

    def __init__(self):
        super(openAeroCode, self).__init__()
        self.basedir = os.path.join(os.getcwd(),"all_runs")
        try:
            os.mkdir(self.basedir)
        except:
            print "failed to make base dir all_runs; or it exists"

    def getRunCaseBuilder(self):
        raise unimplementedError, "this is a \"virtual\" class!"

    def getResults(self, keys, results_dir):
        raise unimplementedError, "this is a \"virtual\" class!"

    def setOutput(self, output_params):
        raise unimplementedError, "this is a \"virtual\" class!"        
    

class openFAST(openAeroCode):
    def __init__(self, geom, atm):
        self.runfast = runFASText(geom, atm)
        super(openFAST, self).__init__()
        print "openFAST __init__"

    def getRunCaseBuilder(self):
        return FASTRunCaseBuilder()

    def configure(self):
        print "openFAST configure"
        self.add('runner', self.runfast)
        self.driver.workflow.add(['runner'])
        self.connect('input', 'runner.input')
        self.connect('runner.output', 'output')        

    def execute(self):
        print "openFAST.execute(), case = ", self.input
        super(openFAST, self).execute()

    def getResults(self, keys, results_dir, operation=max):
        myfast = self.runfast.rawfast        
        col = myfast.getOutputValues(keys, results_dir)
        vals = []
        for i in range(len(col)):
            c = col[i]
            try:
                val = operation(c)
            except:
                val = None
            vals.append(val)
        return vals

    def setOutput(self, output_params):
        self.runfast.set_fast_outputs(output_params['output_keys'])

class designFAST(openFAST):        
    """ base class for cases where we have parametric design (e.g. dakota),
    corresponding to a driver that are for use within a Driver that "has_parameters" """
    x = Array(iotype='in')   ## exact size of this gets filled in study.setup_cases(), which call create_x, below
    f = Float(iotype='out')
    # need some mapping back and forth
    param_names = []

    def __init__(self,geom,atm):
        super(designFAST, self).__init__(geom,atm)

    def create_x(self, size):
        """ just needs to exist and be right size to use has_parameters stuff """
        self.x = [0 for i in range(size)]

    def dlc_from_params(self,x):
        print x, self.param_names, self.dlc.name
        case = FASTRunCaseBuilder.buildRunCase_x(x, self.param_names, self.dlc)
        print case.fst_params
        return case

    def execute(self):
        # build DLC from x, if we're using it
        print "in design code. execute()", self.x
        self.input = self.dlc_from_params(self.x)
        super(designFAST, self).execute()
        myfast = self.runfast.rawfast
        self.f = myfast.getMaxOutputValue('TwrBsMxt', directory=os.getcwd())

class runFASText(ExternalCode):
    """ 
        this is an ExternalCode class to take advantage of file copying stuff.
        then it finally calls the real (openMDAO-free) FAST wrapper 
    """
    input = Slot(RunCase, iotype='in')
    output = Slot(RunResult, iotype='out')  ## never used, never even set

    fast_outputs = ['WindVxi','RotSpeed', 'RotPwr', 'GenPwr', 'RootMxc1', 'RootMyc1', 'LSSGagMya', 'LSSGagMza', 'YawBrMxp', 'YawBrMyp','TwrBsMxt',
                    'TwrBsMyt', 'Fair1Ten', 'Fair2Ten', 'Fair3Ten', 'Anch1Ten', 'Anch2Ten', 'Anch3Ten'] # meant to be overridden by caller
    def __init__(self, geom, atm):
        super(runFASText,self).__init__()
        self.rawfast = runFAST(geom, atm)
#        self.rawfast.setFastFile("MyFastInputTemplate.fst")  # still needs to live in "InputFilesToWrite/"
        self.rawfast.model_path = 'ModelFiles/'
        self.rawfast.template_path = "InputFilesToWrite/"
        self.rawfast.ptfm_file = "NREL5MW_Platform.ptfm"
        self.rawfast.wamit_path = "ModelFiles/WAMIT/spar"

        self.rawfast.setFastFile("NREL5MW_Monopile_Floating.fst")  # still needs to live in "InputFilesToWrite/"
#        self.rawfast.setFastFile("NREL5MW_Monopile_Floating.v7.01.fst")  # still needs to live in "InputFilesToWrite/"

        self.rawfast.setOutputs(self.fast_outputs)

        self.basedir = os.path.join(os.getcwd(),"all_runs")
        try:
            os.mkdir(self.basedir)
        except:
            print "failed to make base dir all_runs; or it exists"
        
        self.copyback_files = True
        
        self.appname = self.rawfast.getBin()
#        template_dir = self.rawfast.getTemplateDir()
#        noiset = os.path.join(template_dir, self.rawfast.noise_template)
#        fastt = os.path.join(template_dir, self.rawfast.template_file)
        noiset = os.path.join("InputFilesToWrite", "Noise.v7.02.ipt")
        adt = os.path.join("InputFilesToWrite", "NREL5MW.ad")
        bladet = os.path.join("InputFilesToWrite", "NREL5MW_Blade.dat")
        ptfmt = os.path.join("InputFilesToWrite", "NREL5MW_Platform.ptfm")
        foundationt = os.path.join("ModelFiles", "NREL5MW_Monopile_Tower_RigFnd.dat")
        spar1 = os.path.join("ModelFiles", os.path.join("WAMIT", "spar.1"))
        spar3 = os.path.join("ModelFiles", os.path.join("WAMIT", "spar.3"))
        sparhst = os.path.join("ModelFiles", os.path.join("WAMIT", "spar.hst"))
#        fastt = os.path.join("InputFilesToWrite", "NREL5MW_Monopile_Rigid.v7.02.fst")
        fastt = os.path.join("InputFilesToWrite",  self.rawfast.fast_file)
        tst = os.path.join("InputFilesToWrite","turbsim_template.inp")
        self.command = [self.appname, "test.fst"]
                
        self.external_files = [
            FileMetadata(path=noiset, binary=False),
            FileMetadata(path=adt, binary=False),
            FileMetadata(path=bladet, binary=False),
            FileMetadata(path=ptfmt, binary=False),
            FileMetadata(path=spar1, binary=False),
            FileMetadata(path=spar3, binary=False),
            FileMetadata(path=sparhst, binary=False),
            FileMetadata(path=foundationt, binary=False), 
            FileMetadata(path=tst, binary=False),
            FileMetadata(path=fastt, binary=False)]
        for nm in self.rawfast.getafNames():  
            self.external_files.append(FileMetadata(path="%s" % nm, binary=False))

    def set_fast_outputs(self,fst_out):
        self.fast_outputs = fst_out
        self.rawfast.setOutputs(self.fast_outputs)
                
    def execute(self):
        # call runFast to just write the inputs
        case = self.input

        ### key moment:
        # transfer info from case to FAST object
        ws=case.fst_params['Vhub']
        if ('RotSpeed' in case.fst_params):
            rpm = case.fst_params['RotSpeed']
        else:
            rpm = 12.03
        self.rawfast.set_ws(ws)
        self.rawfast.set_rpm(rpm)
        # rest of input delivered by line-by-line dictionary case.fst_params in write_inputs()
        
#        self.rawfast.set_wind_file(case.windfile)  ## slows us down a lot, delete for testing; also,
        # overrides given wind speed; but this is what is in RunIEC.pl
        ### end of key moment!

        tmax = 2  ## should not be hard default ##
        if ('TMax' in case.fst_params):  ## Note, this gets set via "AnalTime" in input files--FAST peculiarity ? ##
            tmax = case.fst_params['TMax']

        # run TurbSim to generate the wind:        
        ### Turbsim: this should be higher up the chain in the "assembly": TODO
        ts = runTurbSim()
        ts.set_dict({"URef": ws, "AnalysisTime":tmax, "UsableTime":tmax})
        ts.execute() ## cheating to not use assembly ##
        self.rawfast.set_wind_file("turbsim_test.wnd")
        ### but look how easy it is just to stick it here ?!

        # let the FAST object write its inputs
        self.rawfast.write_inputs(case.fst_params)
        
        ### actually execute FAST (!!) via superclass' system call, command we already set up
        super(runFASText,self).execute()
        ###

        # gather output directly
        self.output = FASTRunResult(self)
        self.rawfast.computeMaxPower()
        
        # also, copy all the output and input back "home"
        if (self.copyback_files):
            self.results_dir = os.path.join(self.basedir, case.name)
            try:
                os.mkdir(self.results_dir)
            except:
                # print 'error creating directory', results_dir
                # print 'it probably already exists, so no problem'
                pass

            # Is this supposed to do what we're doing by hand here?
            # self.copy_results_dirs(results_dir, '', overwrite=True)

            files = glob.glob('test' + '.*')  # TODO: "test" b/c coded into runFAST.py
            for f in glob.glob('NREL' + '*.*'):  # TODO: "NREL" b/c name of template file
                files.append(f)
            files.append('error.out')  #  TODO: other files we need ?
            
            for filename in files:
#                print "wanting to copy %s to %s" % (filename, results_dir) ## for debugging, don't clobber stuff you care about!
                shutil.copy(filename, self.results_dir)



def run_test():
    geometry, atm = makeGeometry()
    w = designFAST(geometry, atm)

    ## sort of hacks to save this info
    w.param_names = ['Vhub']
    w.dlc = FASTRunCase("runAero-testcase", {}, None)
    print "set aerocode dlc"
    ##

    res = []
    for x in range(10,16,2):
        w.x = [x]
        w.execute()
        res.append([ w.dlc.name, w.param_names, w.x, w.f])
    for r in res:
        print r

if __name__=="__main__":
    run_test()
