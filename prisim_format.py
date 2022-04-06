#!/usr/bin/env python3

from growth.plate_spec import PlateSpec
from growth.plate_time_course_parser import SavageLabM1000Excel

import argparse
import numpy as np


if __name__=="__main__":
	parser = argparse.ArgumentParser(description="""Take the output from a tecan 96 or 384 well experiment and a plate map
	  	generate a prisim ready output file from each measurement type""")
	parser.add_argument('-96', dest='plate_size', action='store_const', const=96, default=384,
	                   help='Indicates that the plate should be parsed as a 96 not 384 well plate')
	parser.add_argument('-overflow', type=float, default=np.NAN,
	                   help="""This flag indicates how overflow errors from the tecan should be handled. 
	                   If the flag is not set, The oveflow error will be left blank, if set with the value provided will be used instead""")
	parser.add_argument('plate_map', type=str,
	                   help='The location of the plate map')
	parser.add_argument('tecan_output', type=str,
	                   help='The location of the tecan output')
	parser.add_argument('out_prefix', type=str,
	                   help='The prefix for the prism ready files')

	args = parser.parse_args()

	ps = PlateSpec.FromFile(args.plate_map, plate_size=args.plate_size)

	parser = SavageLabM1000Excel(overflow=args.overflow)
	timecourse = parser.ParseFromFilename(args.tecan_output)

	timecourse.save_data_by_name(ps, args.out_prefix)
