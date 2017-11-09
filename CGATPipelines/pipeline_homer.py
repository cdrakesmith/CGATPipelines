"""====================================================================
pipeline_homer - Produce Peaklist from Bam files using homer software
=======================================================================

Overview
========

The aim of this pipeline is to create peaklists in :term:`bed` files from
aligned reads in :term:`bam` files that can then be taken on to downstream
analysis (e.g., quantification of peaks etc.). Pipeline
also performs motif analysis and basic QC analysis
(i.e., basic tag information, read length distribution, clonal tag distribution
(clonal read depth), autocorrelation analysis (distribution of distances
between adjacent reads in the genome) and sequence bias analysis).

Usage
=====

See :ref:`PipelineSettingUp` and :ref:`PipelineRunning` on general
information how to use CGAT pipelines.

Configuration
=============

The pipeline requires a configured :file:`pipeline.ini` file.
CGATReport report requires a :file:`conf.py` and optionally a
:file:`cgatreport.ini` file (see :ref:`PipelineReporting`).

Default configuration files can be generated by executing:

   python <srcdir>/pipeline_@template@.py config

Functionality
=============

- Takes paired-end or single end :term:`Bam` files you want to call peaks on
  (e.g. ChIP-Seq or ATAC-Seq samples and their appropriate 'input' controls).
- Creates Tag directories for ChIP and Input :term:'Bam' files
- Runs homer peakcaller (findPeaks)
- Produces peak lists in bed files to take forward for downstream analysis.
- Performs motif discovery analysis
- Performs peak annotation
- Finds differential and common  peaks between replicates (reproducibility)
  and between samples (differential binding)

Pipeline Input
==============

Sample_bam = bam file you want to call peaks on (i.e. ChiP Bam or ATAC-Seq Bam)

Input_bam = control file used as background reference in peakcalling
(e.g. input file for ChIP-seq)

pipeline.ini = File containing paramaters and options for
running the pipeline

design.tsv = Design file based on design file for R package DiffBind
Has the following collumns:
SampleID Tissue Factor Condition Treatment Replicate bamReads ControlID bamControl

Pipeline output
===============

The aim of this pipeline is to output a list of peaks that
can be used for further downstream analysis.

The pipeline generates several new files and  directories 
containing output files - these can roughly be grouped into XXX main
stages of the pipeline

1) TagDirectories for each ChIP and Input
   ---------------------------------------
    Directories contain:
    * basic QC analysis results: genomeGCcontent.txt,
      tagAutocorrelation.txt, tagCountDistribution.txt, tagFreq.txt, 
      tagFreqUniq.txt,tagGCcontent.txt, tagInfo.txt,
      tagLengthDistribution.txt
    * called peaks in :term:'bed' and :term:'txt' formats
    * peak annotations
    * Motif analysis results: homerResults and knownResults


2) Replicates.dir
   ---------------
    Directory contains:

3) Peaks.dir
   ---------------
    Directory contains:
    

Code
====

"""
# load modules
from ruffus import *
import sys
import os
import CGAT.Experiment as E
import CGATPipelines.Pipeline as P
import CGATPipelines.PipelinePeakcalling as PipelinePeakcalling
import CGAT.BamTools as Bamtools


#########################################################################
# Load PARAMS Dictionary from Pipeline.ini file options #################
#########################################################################

PARAMS = P.getParameters(
    ["%s/pipeline.ini" % os.path.splitext(__file__)[0],
     "../pipeline.ini",
     "pipeline.ini"])


#######################################################################
# Check for design file & Match ChIP/ATAC-Seq Bams with Inputs ########
#######################################################################

# This section checks for the design table and generates:
# 1. A dictionary, inputD, linking each input file and each of ChIP sample
#    as specified in the design table
# 2. A pandas dataframe, df, containing the information from the
#    design table.
# 3. INPUTBAMS: a list of control (input) bam files to use as background for
#    peakcalling.
# 4. CHIPBAMS: a list of experimental bam files on which to call peaks on.

# if design table is missing the input and chip bams to empty list. This gets
# round the import tests

if os.path.exists("design.tsv"):
    df, inputD = PipelinePeakcalling.readDesignTable("design.tsv",
                                                     PARAMS['IDR_poolinputs'])
    INPUTBAMS = list(set(df['bamControl'].values))
    CHIPBAMS = list(set(df['bamReads'].values))


else:
    E.warn("design.tsv is not located within the folder")
    INPUTBAMS = []
    CHIPBAMS = []


########################################################################
# Check if reads are paired end ########################################
########################################################################

if CHIPBAMS and Bamtools.isPaired(CHIPBAMS[0]) is True:
    PARAMS['paired_end'] = True
else:
    PARAMS['paired_end'] = False


#########################################################################
# Connect to database ###################################################
#########################################################################

def connect():
    '''
    Setup a connection to an sqlite database
    '''

    dbh = sqlite3.connect(PARAMS['database'])
    return dbh

###########################################################################
# start of pipelined tasks ################################################
# Preprocessing Steps - Filter bam files & generate bam stats #############
###########################################################################

@transform("design.tsv", suffix(".tsv"), ".load")
def loadDesignTable(infile, outfile):
    ''' load design.tsv to database '''
    P.load(infile, outfile)


###########################################################################
# makeTagDirectory Inputs #################################################
###########################################################################

@follows(loadDesignTable)
@transform(INPUTBAMS, regex("(.*).bam"),
           r"\1/\1.txt")
def makeTagDirectoryInput(infile, outfile):
    '''This will create an input tag file for each sam file
    converted from a given bam file
    for a CHIP-seq experiment
    It will also evaluate the GC content of the reads.
    '''

    bamstrip = infile.strip(".bam")
    samfile = bamstrip + ".sam"

    statement = '''samtools index %(infile)s;
                   samtools view %(infile)s > %(samfile)s;
                   makeTagDirectory
                   -genome %(maketagdir_genome)s -checkGC
                   %(bamstrip)s/ %(samfile)s
                   &> %(bamstrip)s.makeTagInput.log;
                   touch %(bamstrip)s/%(bamstrip)s.txt'''

    P.run()


###########################################################################
# makeTagDirectory ChIPs ##################################################
###########################################################################

@follows(loadDesignTable)
@transform(CHIPBAMS, regex("(.*).bam"),
           r"\1/\1.txt")
def makeTagDirectoryChips(infile, outfile):
    '''This will create a ChIP  tag file for each sam file
    coonverted from a given bam file
    for a CHIP-seq experiment.
    It will also evaluate the GC content of the reads.
    '''

    bamstrip = infile.strip(".bam")
    samfile = bamstrip + ".sam"

    statement = '''samtools index %(infile)s;
                   samtools view %(infile)s > %(samfile)s;
                   makeTagDirectory
                   %(bamstrip)s/ %(samfile)s
                   -genome %(maketagdir_genome)s -checkGC
                   &> %(bamstrip)s.makeTagChip.log;
                   touch %(bamstrip)s/%(bamstrip)s.txt'''

    P.run()



###########################################################################
# Homer peak calling task #################################################
###########################################################################

@transform((makeTagDirectoryChips),
           regex("(.*)/(.*).txt"),
           r"\1/regions.txt")
def findPeaks(infile, outfile):

    '''
    Arguments
    ---------
    infiles : string
         this is a list of tag directories
    directory: string
         This is the directory where the tag file will be placed
    '''

    directory = infile.strip(".txt")
    directory, _ = directory.split("/")
    bamfile = directory + ".bam"

    df_slice = df[df['bamReads'] == bamfile]
    input_bam = df_slice['bamControl'].values[0]
    input_bam = input_bam.strip(".bam")

    statement = '''findPeaks %(directory)s -style %(findpeaks_style)s -o %(findpeaks_output)s
                   %(findpeaks_options)s -i %(input_bam)s &> %(directory)s.findpeaks.log'''
    P.run()



@transform(findPeaks,
           regex("(.*)/regions.txt"),
           r"\1/\1.bed")
def bedConversion(infile, outfile):

    '''This will generate :term:`bed` files from
    created :term:`txt` files
    '''

    statement = '''pos2bed.pl %(BED_options)s %(infile)s > %(outfile)s'''

    P.run()


###########################################################################
# Called peak annotations #################################################
###########################################################################

@transform(findPeaks,
           regex("(.*)/regions.txt"),
           r"\1/annotate.txt")
def annotatePeaks(infile, outfile):

    '''This will generate annotations of
    genomic regions of the called peaks by associating
    them with nearby genes
    '''

    statement = '''annotatePeaks.pl %(infile)s %(annotatePeaks_genome)s &> Annotate.log > %(outfile)s'''

    P.run()



###########################################################################
# Homer motif analysis ####################################################
###########################################################################

@transform(findPeaks,
           regex("(.*)/regions.txt"),
           r"\1/motifs.txt")
def findMotifs(infile, outfile):

    '''
    This will manage the steps for discovering motifs in genomic regions
    and will generate de novo and known motif results and will provide the
    associated statistics
    '''

    directory, _ = infile.split("/")

    statement = '''findMotifsGenome.pl %(infile)s %(motif_genome)s %(directory)s -size %(motif_size)i
                   &> Motif.log'''

    P.run()


###########################################################################
# Get differential binding profiles  between different ChIP samples #######
###########################################################################

@merge(makeTagDirectoryChips, "countTable.peaks.txt")
def annotatePeaksRaw(infiles, outfile):
    
    '''
    Calculates and reports integer read counts for
    ChIP-Seq tag densities across different experiments
    '''

    directories = []
    for infile in infiles:
        directory = infile.split("/")[0]
        directories.append(directory + "/")

    directories = " ".join(directories)

    statement = '''annotatePeaks.pl %(annotate_raw_region)s %(annotate_raw_genome)s
                   -d %(directories)s > countTable.peaks.txt'''

    P.run()


@transform(annotatePeaksRaw,
           suffix(".peaks.txt"),
           ".diffexprs.txt")


def getDiffExprs(infile, outfile):

    '''
    Compares raw read counts generated by annotatePeaksRaw function
    across different experiments
    '''

    statement = '''getDiffExpression.pl %(infile)s
                  %(diff_expr_options)s %(diff_expr_group)s > diffOutput.txt'''

    P.run()


###########################################################################
# Get differentially called peaks between ChIP sample replicates to check #
######################### replicate reproducibility #######################
###########################################################################

# ruffus decorator is wrong but it needs changhing later
@follows(mkdir("Replicates.dir"))
@follows(makeTagDirectoryChips)
@originate("Replicates.dir/outputPeaks.txt")
def getDiffPeaksReplicates(outfile):

    '''
    Identifies peaks from replicates with the output files containing
    annotation, normalised read counts, and differential enrichment
    statistics
    '''

    replicates = set(df["Replicate"])

    for x in replicates:
        subdf = df[df["Replicate"] == x]

        bams = subdf["bamReads"].values

        bam_strip = []
        for bam in bams:
            bam = bam.strip(".bam") + "/"
            bam_strip.append(bam)

    bam_strip = " ".join(bam_strip)

    inputs = subdf["bamControl"].values

    input_strip = []
    for inp in inputs:
        inp = inp.strip(".bam") + "/"
        input_strip.append(inp)

    input_strip = " ".join(input_strip)

    statement = '''getDifferentialPeaksReplicates.pl -t %(bam_strip)s
                       -i %(input_strip)s -genome %(diff_repeats_genome)s %(diff_repeats_options)s>
                       Replicates.dir/Repeat-%(x)s.outputPeaks.txt'''

    P.run()


# ---------------------------------------------------
# Generic pipeline tasks


@follows(loadDesignTable,
         bedConversion,
         annotatePeaks,
         annotatePeaksRaw,
         getDiffExprs,
         getDiffPeaksReplicates,
         findMotifs)
def full():
    pass


@follows(mkdir("Jupyter_report.dir"))
def renderJupyterReport():
    '''build Jupyter notebook report'''

    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                               'pipeline_docs',
                                               'pipeline_homer',
                                               'Jupyter_report'))

    statement = ''' cp %(report_path)s/* Jupyter_report.dir/ ; cd Jupyter_report.dir/;
                    jupyter nbconvert --ExecutePreprocessor.timeout=None --to html --execute *.ipynb;
                 '''

    P.run()


# We will implement this when the new version of multiqc is available
@follows(mkdir("MultiQC_report.dir"))
@originate("MultiQC_report.dir/multiqc_report.html")
def renderMultiqc(infile):
    '''build mulitqc report'''

    statement = '''LANG=en_GB.UTF-8 multiqc . -f;
                   mv multiqc_report.html MultiQC_report.dir/'''

    P.run()


@follows(renderJupyterReport)
def build_report():
    pass


def main(argv=None):
    if argv is None:
        argv = sys.argv
    P.main(argv)


if __name__ == "__main__":
    sys.exit(P.main(sys.argv))
