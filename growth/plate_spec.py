#!/usr/bin/python

import pandas as pd
import numpy as np
import itertools


class PlateSpec(dict):
    """Read/write specifications for 96 well plates.

    TODO: make this generic for any plate size.
    """

    def __init__(self, df, plate_size=96):
        """Initialize with a DataFrame describing the plate.
    
        Args:
            df: Pandas DataFrame. See
                plate_specs/example_plate_spec.csv
                for format.
        """
        if plate_size==96:
            self.COLS = list(map(str, np.arange(1, 13)))
            self.ROWS = 'A,B,C,D,E,F,G,H'.split(',')
        elif plate_size==384:
            self.COLS = list(map(str, np.arange(1, 25)))
            self.ROWS = 'A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P'.split(',')
        else:
            raise NotImplementedError('Plate spec not implemented for plate_size = %s'%plate_size)

        assert (df.shape[0] == len(self.ROWS)) & (df.shape[1] == len(self.COLS)), "df size: %s does not match plate_size %s"%(df.shape, (len(self.ROWS), len(self.COLS)))
        self.df = df

    def well_to_name_mapping(self):
        """Returns a mapping from cells -> name."""
        rows = self.ROWS
        cols = self.COLS
        mapping = dict()
        for row, col in itertools.product(rows, cols):
            s = '%s%s' % (row, col)
            try:
                n = self.df.name[col][row]
            except:
                print(rows)
                print(row)
                print(cols)
                print(col)
                print(s)
                raise ValueError
            mapping[s] = n
        return mapping

    def name_to_well_mapping(self):
        """Returns a mapping from name -> cells."""
        rows = self.ROWS
        cols = self.COLS
        mapping = dict()
        for row, col in itertools.product(rows, cols):
            s = '%s%s' % (row, col)
            try:
                n = self.df.name[col][row]
            except:
                print(rows)
                print(row)
                print(cols)
                print(col)
                print(s)
                raise ValueError
            mapping.setdefault(n, []).append(s)
        return mapping

    @staticmethod
    def NullPlateSpec(plate_size=96):
        """
        Returns an empty PlateSpec in the right format for 96 well plates.
        """
        rows = self.ROWS
        cols = self.COLS

        arrays = [['name'], cols]
        tuples = list(itertools.product(*arrays))

        index = pd.MultiIndex.from_tuples(
            tuples, names=['value_type', 'column'])
        well_names = []
        for row in rows:
            row_data = []
            for col in cols:
                s = '%s%s' % (row, col)
                row_data.append(s)
            well_names.append(row_data)

        df = pd.DataFrame(well_names, index=rows, columns=index)
        return PlateSpec(df, plate_size=plate_size)

    @staticmethod
    def FromFile(f, plate_size=96):
        """Assumes f is a CSV file.

        Args:
            f: file handle or path to read from.
                Better be in the right format.
        """
        df = pd.read_csv(f, header=[0, 1], index_col=[0])
        return PlateSpec(df, plate_size=plate_size)
