#########################################################################
#
#   MRC FGU Computational Genomics Group
#
#   $Id: cgat_script_template.py 2871 2010-03-03 10:20:44Z andreas $
#
#   Copyright (C) 2009 Andreas Heger
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
##########################################################################
'''
PipelineSplicing.py - wrap various differential expression tools
===========================================================

:Author: Andreas Heger
:Release: $Id$
:Date: |today|
:Tags: Python

Purpose
-------

This module provides tools for differential splicing analysis
for a variety of methods.

Methods implemented are:

   DEXSeq
   rMATS

The aim of this module is to run these individual tools and
output a table in a common format.

Usage
-----

Documentation
-------------

Requirements:

* DEXSeq >= ?
* rMATS >= ?



'''

import sys
import rpy2
from rpy2.robjects import r as R
import rpy2.robjects as ro
from rpy2.robjects import pandas2ri
from rpy2.robjects.packages import importr
from rpy2.robjects.vectors import FloatVector
from ruffus import *
import os
import glob
import sqlite3
import CGAT.BamTools as BamTools
import CGAT.Experiment as E
import CGAT.Expression as Expression
import CGATPipelines.Pipeline as P
import CGATPipelines.PipelineTracks as PipelineTracks


class Splicer(object):
    ''' base clase for DS experiments '''

    def __init__(self, gtf, design):
        self.gtf = gtf

    def __call__(self):
        ''' call DS and generate an initial results table '''
        self.callDifferentialSplicing()

    def preprocess(self):
        ''' Processing of BAM file to desired format'''
        return ""

    def splicer(Self):
        ''' Custom DS functions '''
        return ""

    def visualise(self):
        ''' Visualise results using plots'''
        return ""

    def build(self, infiles, outfile):
        '''run mapper

        This method combines the output of the :meth:`preprocess`,
        :meth:`mapper`, :meth:`postprocess` and :meth:`clean` sections
        into a single statement.

        Arguments
        ---------
        infiles : list
             List of input filenames
        outfile : string
             Output filename

        Returns
        -------
        statement : string
             A command line statement. The statement can be a series
             of commands separated by ``;`` and/or can be unix pipes.

        '''

        cmd_preprocess = self.preprocess(infiles, outfile)
        cmd_splicer = self.splicer(design, outfile)
        cmd_visualise = self.visualise(infiles, outfile)
        cmd_clean = self.cleanup(outfile)

        assert cmd_preprocess.strip().endswith(";"),\
            "missing ';' at end of command %s" % cmd_preprocess.strip()
        assert cmd_mapper.strip().endswith(";"),\
            "missing ';' at end of command %s" % cmd_mapper.strip()
        if cmd_postprocess:
            assert cmd_postprocess.strip().endswith(";"),\
                "missing ';' at end of command %s" % cmd_postprocess.strip()
        if cmd_clean:
            assert cmd_clean.strip().endswith(";"),\
                "missing ';' at end of command %s" % cmd_clean.strip()

        statement = " checkpoint; ".join((cmd_preprocess,
                                          cmd_mapper,
                                          cmd_postprocess,
                                          cmd_clean))

        return statement


class rMATS(Splicer):
    '''DEExperiment object to generate differential splicing events
       using rMATS
    '''

    def __init__(self, executable="rMATS", pvalue=0.05,
                 *args, **kwargs):
        Splicer.__init__(self, *args, **kwargs)

        self.executable = executable
        self.pvalue = pvalue

    def splicer(self,
                design,
                outfile_prefix=None):

        self.design = design

        group1 = ",".join(
            ["%s.bam" % x for x in design.getSamplesInGroup(design.groups[0])])
        group2 = ",".join(
            ["%s.bam" % x for x in design.getSamplesInGroup(design.groups[1])])
        readlength = BamTools.estimateTagSize(design.samples[0]+".bam")

        statement = '''%(self.executable)s
        -b1 %(group1)s
        -b2 %(group2)s
        -gtf %(self.gtf)s)
        -o %(outfile)s
        -len %(readlength)s
        -c %(self.pvalue)s
        ''' % locals()

        # Specify paired design
        if design.has_pairs:
            statement += "-analysis P "

            # Get Insert Size Statistics if Paired End Reads
            if BamTools.isPaired(design.samples[0]+".bam"):
                inserts1 = [BamTools.estimateInsertSizeDistribution(sample+".bam", 10000)
                            for sample in design.getSamplesInGroup(design.groups[0])]
                inserts2 = [BamTools.estimateInsertSizeDistribution(sample+".bam", 10000)
                            for sample in design.getSamplesInGroup(design.groups[1])]
                r1 = ",".join(map(str, [item[0] for item in inserts1]))
                sd1 = ",".join(map(str, [item[1] for item in inserts1]))
                r2 = ",".join(map(str, [item[0] for item in inserts2]))
                sd2 = ",".join(map(str, [item[1] for item in inserts2]))

                statement += '''-t paired
                -r1 %(r1)s -r2 %(r2)s
                -sd1 %(sd1)s -sd2 %(sd2)s''' % locals()

        return statement


class DEXSeq(Splicer):
    '''DEExperiment object to generate differential splicing events
       using DEXSeq
    '''

    def __init__(self, executable="rMATS", pvalue=0.05,
                 *args, **kwargs):
        Splicer.__init__(self, *args, **kwargs)

        self.executable = executable
        self.pvalue = pvalue

    def run(self,
            design,
            outfile_prefix=None):

        return
