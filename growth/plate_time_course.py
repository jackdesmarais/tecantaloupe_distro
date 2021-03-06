#!/usr/bin/python

from scipy import stats
from scipy import integrate
import matplotlib.colors as colors
import numpy as np
import pandas as pd
import pylab
import logging

logger = logging.getLogger('plate_time_course')
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class PlateTimeCourse(object):
    """Immutable plate data with convenience methods for computations."""

    TEMP_COL = 'temp_C'
    TIME_COL = 'time_s'
    SPECIAL_COLS = (TEMP_COL, TIME_COL)

    def __init__(self, well_df):
        self._well_df = well_df  # Immutable

    @property
    def well_df(self):
        """Returns a DataFrame with data of this well.

        TODO: document well_df format.
        """
        return self._well_df

    def labels(self):
        return self._well_df.columns.levels[0].tolist()

    def _filter_columns(self, cols):
        cs = [c for c in cols if c != self.TEMP_COL]
        return cs

    def data_for_plate_wells(self, wells):
        """Grab data only for these wells.

        Returns:
            A new PlateTimeCourse object.
        """
        sorted = self._well_df.sort_index(axis=1)
        
        # keep time column always
        selector = wells + [self.TIME_COL]
        sub_df = self._well_df.loc[:, (slice(None), selector)]
        return PlateTimeCourse(sub_df)

    def data_for_plate_rows(self, rows):
        """Grab only data for these plate rows.

        As opposed to DataFrame rows.

        Returns:
            A new PlateTimeCourse object.
        """
        wells = ['%s%s' % (r, c) for r in rows
                 for c in np.arange(1, 13)]
        # keep time column always
        return self.data_for_plate_wells(wells)

    def data_for_plate_cols(self, cols):
        """Grab only data for these plate columns.

        As opposed to DataFrame columns.

        Returns:
            A new PlateTimeCourse object.
        """
        wells = ['%s%s' % (r, c) for r in 'ABCDEFGH'
                 for c in cols]
        # keep time column always
        return self.data_for_plate_wells(wells)

    def data_for_label(self, label):
        """Returns data for this label.

        Removes the cycle nr. and temp data since
        they get in the way of plotting.
        """
        failure_msg = 'No such label "%s"' % label
        assert label in self._well_df.columns, failure_msg
        data = self._well_df[label]
        data_cols = self._filter_columns(data.columns)
        return data[data_cols]

    def _blank_by_blank_wells(self, blank_wells, n_skip=3, n_av=5):
        """Return a new timecourse that has been blanked.

        TODO: blanking based on separate blank wells should be possible.
        Need to think about that, though, cuz you might have multiple blanks
        with different media which could not be averaged.

        Args:
            n_skip: number of initial points to skip.
            n_av: number of initial points to average on a per-well basis.
        """
        wdf = self._well_df
        index = wdf.index
        pos_to_average = index[n_skip:n_skip+n_av]

        blanked_df = wdf.copy()  # modify a copy

        for dtype in wdf.columns.levels[0]:
            # blank each datatype separately
            sub_df = wdf[dtype]
            cols = set(sub_df.columns)
            cols_to_use = cols.difference(self.SPECIAL_COLS)
            cols_to_use = list(cols_to_use)

            blank_vals = []
            for colname in sub_df.columns:
                if colname not in blank_wells:
                    # don't blank cycle numbers or temperatures.
                    continue

                vals_to_av = sub_df[colname].loc[pos_to_average]
                blank_vals.extend(vals_to_av.values)

            blank_val = np.mean(blank_vals)
            blanked_df.loc[:, (dtype, cols_to_use)] -= blank_val

        return PlateTimeCourse(blanked_df)

    def _blank_by_early_timepoints(self, n_skip=3, n_av=5):
        """Return a new timecourse that has been blanked.

        Args:
            n_skip: number of initial points to skip.
            n_av: number of initial points to average on a per-well basis.
        """
        # Subtract off the mean of the 5 lowest recorded values
        # for each time series.
        corrected_df = self._well_df.copy()
        index = corrected_df.index
        pos_to_average = index[n_skip:n_skip+n_av]

        for key, values in corrected_df.iteritems():
            colname = key[1]
            if colname in (self.TIME_COL, self.TEMP_COL):
                # don't blank cycle numbers or temperatures.
                continue

            vals_to_av = corrected_df[key].loc[pos_to_average]
            corrected_df[key] -= vals_to_av.mean()

        return PlateTimeCourse(corrected_df.dropna(how='any', axis=0))

    def blank(self, blank_wells=None, n_skip=3, n_av=5):
        """Return a new timecourse that has been blanked.

        If blank_wells is defined, all wells will be blanked
        according to the mean measurements of n_av early timepoints
        from the defined blanks.

        Otherwise, each well will be blanked separately by subtracting
        off the mean of n_av early timepoints (skipping the first n_skip).

        Args:
            blank_wells: the column IDs of blank wells.
            n_skip: number of initial points to skip.
            n_av: number of initial points to average on a per-well basis.
        """
        if not blank_wells:
            return self._blank_by_early_timepoints(
                n_skip=n_skip, n_av=n_av)
        return self._blank_by_blank_wells(
            blank_wells, n_skip=n_skip, n_av=n_av)

    def smooth(self, window=3, rounds=2):
        """Smooth your data to average out blips.

        TODO: this is also doing a rolling mean on the time
        and temp. Should exclude these from the smoothing.

        Args:
            window: the number of measurements to include
                in the rolling mean window.
            rounds: the number of rounds of smoothing to do.

        Returns:
            A new PlateTimeCourse with the averaged data.
        """
        logging.debug('in smooth')
        assert rounds > 0

        smoothed = self._well_df.copy()
        logging.debug('made df copy')
        for _ in range(rounds):
            for key, row in smoothed.iteritems():
                colname = key[1]
                if colname in self.SPECIAL_COLS:
                    # don't smooth cycle numbers or temperatures.
                    continue

                logging.debug('about to rolling')
                smoothed[key] = row.rolling(window).mean()
                logging.debug('rolled')

        return PlateTimeCourse(smoothed.dropna(how='any', axis=0))

    def ratio_time_course(self, numerator, denominator):
        """Returns a time course of the ratio of two measurements.

        Args:
            numerator: string label of the numerator of the ratio.
            denominator: string label of the denominator of the ratio.

        Returns:
            A new PlateTimeCourse with a measureming called
                "numerator/denominator."
        """
        num = self.data_for_label(numerator)
        denom = self.data_for_label(denominator)

        num_data = num.drop('time_s', axis=1)
        denom_data = denom.drop('time_s', axis=1)

        name = '%s/%s' % (numerator, denominator)
        ratio_df = num_data / denom_data

        # numerator is the time standard.
        ratio_df[self.TIME_COL] = num[self.TIME_COL]
        full_df = pd.concat(
            [ratio_df], axis=1, keys=[name],
            names=['measurement_type', 'label'])
        return PlateTimeCourse(full_df)

    def save_data_by_name(self, plate_spec, out):
        """Organise and save data grouped into replicates. Saves a csv for each measurement type

        Returns organized dfs for each measurement type as a dict"""

        mapping = plate_spec.well_to_name_mapping()
        orginized = {}

        labels = self.labels()
        for label_name in labels:
            label_df = self._well_df[label_name]
            mapped = label_df.copy()
            ind = pd.MultiIndex.from_arrays([mapped.columns.map(mapping), mapped.columns], sortorder=0, 
                                names=['Experiment','Cycle_N'])
            mapped.columns=ind
            sort = mapped.sort_index(na_position='first',axis=1)
            sort.index.name = None
            sort.to_csv(out+'_'+label_name+'.csv')
            orginized[label_name] = sort

        return(orginized)




    def mean_by_name(self, plate_spec):
        """Aggregate cells by PlateSpec name, return means.

        Returns means as a DataFrame.

        This should probably return a PlateTimeCourse object?
        """
        mapping = plate_spec.well_to_name_mapping()
        means = []

        labels = self.labels()
        for label_name in labels:
            label_df = self._well_df[label_name]
            grouped = label_df.groupby(mapping, axis=1)
            group_means = grouped.mean()
            group_means[self.TIME_COL] = label_df[self.TIME_COL]
            means.append(group_means)

        keys = self._well_df.columns.levels[0]
        merged_df = pd.concat(
            means, axis=1, keys=keys,
            names=['measurement_type', 'label'])

        return PlateTimeCourse(merged_df)

    def sem_by_name(self, plate_spec):
        """Aggregate cells by PlateSpec name, return SEM.

        Returns standard error of the mean as a DataFrame.

        This should probably return a PlateTimeCourse object?
        """
        mapping = plate_spec.well_to_name_mapping()
        sems = []

        logging.debug('Made starting maps')
        labels = self.labels()
        logging.debug('got labels')
        for label_name in labels:
            logging.debug('label_name: %s'%label_name)
            label_df = self._well_df[label_name]
            logging.debug('got label_df')
            logging.debug('Nan vals: %s'%label_df.isnull().sum(axis=1))
            # label_df=label_df.dropna(how='any', axis=1)

            # if label_df.isnull().sum(axis=1)[label_df.tail(1).index].any()>0:
            #     logging.error('Last line has has Nans, clipping')
            #     label_df.drop(label_df.tail(1).index, inplace=True)
            logging.debug('label_df: %s'%label_df)
            grouped = label_df.groupby(mapping, axis=1)
            logging.debug('groupby')
            logging.debug('last_valid index: %s'%label_df.last_valid_index())
            logging.debug('Nan vals: %s'%label_df.isnull().sum(axis=1))
            logging.debug('Nan vals: %s'%label_df.isnull().sum().sum())
            group_sems = grouped.sem()
            logging.debug('got sem from group')
            group_sems[self.TIME_COL] = label_df[self.TIME_COL]
            logging.debug('reset time col')
            sems.append(group_sems)
            logging.debug('appended sems')

        logging.debug('out of loop')
        keys = self._well_df.columns.levels[0]
        logging.debug('got keys')
        merged_df = pd.concat(
            sems, axis=1, keys=keys,
            names=['measurement_type', 'label'])
        logging.debug('did concat')

        return PlateTimeCourse(merged_df)

    def std_by_name(self, plate_spec):
        """Aggregate cells by PlateSpec name, return std.

        Returns standard deviation of the mean as a DataFrame.

        This should probably return a PlateTimeCourse object?
        """
        mapping = plate_spec.well_to_name_mapping()
        sems = []

        labels = self.labels()
        for label_name in labels:
            label_df = self._well_df[label_name]
            grouped = label_df.groupby(mapping, axis=1)
            group_sems = grouped.std()
            group_sems[self.TIME_COL] = label_df[self.TIME_COL]
            sems.append(group_sems)

        keys = self._well_df.columns.levels[0]
        merged_df = pd.concat(
            sems, axis=1, keys=keys,
            names=['measurement_type', 'label'])

        return PlateTimeCourse(merged_df)

    def GrowthYield(self, density_label='OD600'):
        """Computes the maximum density of the culture.

        Calculated as the maximum observed density.
        Recommended that you blank and smooth first.

        Returns:
            A dictionary mapping column names to growth yield.
        """
        OD_data = self.data_for_label(density_label)
        cols = set(OD_data)
        cols_to_use = cols.difference(self.SPECIAL_COLS)

        yields = dict((col, np.nanmax(OD_data[col].values))
                      for col in cols_to_use)
        return yields

    def TimeToHalfMax(self, density_label='OD600'):
        """Computes the time to half max of the culture.

        Calculated as the time to first exceed the half maximum observed value.
        Recommended that you blank and smooth first.

        Returns:
            A dictionary mapping column names to growth yield.
        """
        OD_data = self.data_for_label(density_label)
        OD_data = OD_data.dropna()
        cols = set(OD_data)
        cols_to_use = cols.difference(self.SPECIAL_COLS)
        tthm = dict((col, OD_data.time_s[(OD_data[col]>=np.max(OD_data[col].values)/2).idxmax()])
                      for col in cols_to_use)
        return tthm

    def AreaUnderTheCurve(self, density_label='OD600'):
        """Computes the integral of the culture densiity using the trapazoid rule

        Recommended that you blank and smooth first.

        added by JJD

        Returns:
            A dictionary mapping column names to integral.
        """
        OD_data = self.data_for_label(density_label)
        OD_data = OD_data.dropna()
        cols = set(OD_data)
        cols_to_use = cols.difference(self.SPECIAL_COLS)
        aoc = dict((col, np.trapz(OD_data[col].values,x=OD_data[self.TIME_COL]))
                      for col in cols_to_use)
        return aoc

    def LagTime(self, density_label='OD600', min_reading=0.1):
        """Returns the lag time in hrs.

        Lag time is here defined as the time at which the culture
        becomes measurable, i.e. crosses the min_reading threshold.

        Returns:
            A dictionary mapping column to lag time in hrs.
        """
        OD_data = self.data_for_label(density_label)
        cols = set(OD_data)
        cols_to_use = cols.difference(self.SPECIAL_COLS)
        cols_to_use = list(cols_to_use)
        time_h = OD_data[self.TIME_COL] / (60.0*60.0)

        # pick timepoint with min abs difference from min_reading
        thresholded = np.abs(OD_data[cols_to_use] - min_reading)
        min_idxs = thresholded.idxmin()

        lags = {}
        for k, idx in min_idxs.iteritems():
            t = time_h[idx]
            lags[k] = t

        max_od = OD_data[cols_to_use].max()
        for k, max_od in max_od.iteritems():
            if max_od < min_reading:
                lags[k] = np.NAN

        return lags

    def GrowthRates(self, density_label='OD600'):
        """Computes the exponential growth rate in gens/hr.

        Returns the local growth rate over time of a 4 measurement window.

        Definitely best to smooth before applying this logic since it
        assumes that derivative(ln(OD)) is smooth.

        TODO: integrate with below? 

        Returns:
            DataFrame of growth rate over time.
        """
        OD_data = self.data_for_label(density_label)
        cols = set(OD_data)
        cols_to_use = cols.difference(self.SPECIAL_COLS)
        time_h = OD_data[self.TIME_COL] / (60.0*60.0)

        growth_rates = {}

        for col in cols_to_use:
            well_data = OD_data[col]
            log_data = np.log(well_data)
            well_slopes = []

            # For each 4-measurement windows.
            # regress against time, keep regression slope.
            for idx in range(len(well_data) - 3):
                local_data = well_data[idx:idx+4].values
                timepoints = time_h[idx:idx+4].values
                regressed = stats.linregress(timepoints, local_data)
                well_slopes.append(regressed[0])

            growth_rates[col] = well_slopes

        growth_rates[self.TIME_COL] = OD_data[self.TIME_COL][:-3]
        return pd.DataFrame(growth_rates)

    def MaxGrowthRates(self, density_label='OD600', min_reading=0.05):
        """Computes the exponential growth rates in gens/hr.

        Maximal growth rate is calculated as the maximal
        exponential growth rate in the growth curve after it crosses
        "min_reading" threshold.

        Definitely best to smooth before applying this logic since it
        assumes that derivative(ln(OD)) is smooth.

        Returns:
            A dictionary mapping column names to growth rates.
        """
        log_lb = np.log(min_reading)
        OD_data = self.data_for_label(density_label)
        cols = set(OD_data)
        cols_to_use = cols.difference(self.SPECIAL_COLS)
        time_h = OD_data[self.TIME_COL] / (60.0*60.0)

        growth_rates = {}

        for col in cols_to_use:
            well_data = OD_data[col]
            log_data = np.log(well_data)
            well_slopes = []

            # For each 4-measurement windows.
            # 1) discard if minimum value beneath user-defined limit.
            # 2) regress against time.
            # 3) keep regression slope.
            for idx in range(len(well_data) - 3):
                local_data = well_data[idx:idx+4].values
                
                if np.nanmin(local_data) < log_lb:
                    well_slopes.append(0.0)
                    continue

                timepoints = time_h[idx:idx+4].values
                regressed = stats.linregress(timepoints, local_data)
                well_slopes.append(regressed[0])

            growth_rates[col] = np.nanmax(well_slopes)

        return growth_rates

