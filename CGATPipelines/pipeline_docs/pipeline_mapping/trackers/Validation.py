
from CGATReport.Tracker import *
from MappingReport import *


class ExonValidationSummary(MappingTracker, SingleTableTrackerRows):
    table = "exon_validation"
