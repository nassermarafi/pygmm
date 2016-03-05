"""Class definition from which all models are based on."""

from __future__ import division

import logging
import os

import numpy as np

# Conversion from cm/sec/sec to gravity
# TO_GRAVITY = 0.00101971621
# FROM_GRAVITY = 1. / TO_GRAVITY


class Model(object):
    """Abstract class for ground motion prediction models.

    Compute the response predicted the model.

    No default implementation.
    """

    NAME = ''
    ABBREV = ''

    INDICES_PSA = np.array([])
    PERIODS = np.array([])
    INDEX_PGA = None
    INDEX_PGV = None
    INDEX_PGD = None

    LIMITS = dict()

    PARAMS = []

    # Scale factor to apply to get PGV in cm/sec
    PGV_SCALE = 1.
    # Scale factor to apply to get PGD in cm
    PGD_SCALE = 1.

    def __init__(self, **kwds):
        super(Model, self).__init__()

        self._ln_resp = None
        self._ln_std = None

        # Select the used parameters and check them against the recommended
        # values
        self.params = {p.name: kwds.get(p.name, None) for p in self.PARAMS}
        self._check_inputs()

    def interp_spec_accels(self, periods):
        """Return the pseudo-spectral acceleration at the provided damping
        at specified periods.

        Inputs:
            period: :class:`numpy.array`
                periods of interest (sec).

        Return
            :class:`numpy.array`
                pseudo-spectral accelerations.

        """

        return np.exp(np.interp(
            np.log(periods),
            np.log(self.periods),
            self._ln_resp[self.INDICES_PSA]))

    def interp_ln_stds(self, periods):
        """Return the logarithmic standard deviation
        (:math:`\\sigma_{ \\ln}`) of spectral acceleration at the provided
        damping at specified periods.


        Inputs:
            period: :class:`numpy.array`
                periods of interest (sec).

        Returns:
            :class:`numpy.array`
                pseudo-spectral accelerations.

        """

        return np.interp(np.log(periods),
                         np.log(self.periods), self._ln_std[self.INDICES_PSA])

    @property
    def periods(self):
        """Periods specified by the model.

        Returns:
            :class:`numpy.array`
        """

        return self.PERIODS[self.INDICES_PSA]

    @property
    def spec_accels(self):
        """Pseudo-spectral accelerations computed by the model (g).

        Returns:
            :class:`numpy.array`
        """

        return self._resp(self.INDICES_PSA)

    @property
    def ln_stds(self):
        """Logarithmic standard deviation of the pseudo-spectral accelerations.

        Returns:
            :class:`numpy.array`
        """

        return self._ln_std[self.INDICES_PSA]

    @property
    def pga(self):
        """Peak ground acceleration (PGA) computed by the model (g).

        Returns:
            :class:`float`

        Raises:
            NotImplementedError
                If model does not provide an estimate.
        """

        if self.INDEX_PGA is None:
            return NotImplementedError
        else:
            return self._resp(self.INDEX_PGA)

    @property
    def ln_std_pga(self):
        """Logarithmic standard deviation (:math:`\\sigma_{ \\ln}`) of the
        peak ground acceleration computed by the model.

        Returns:
            :class:`float`

        Raises:
            NotImplementedError
                If model does not provide an estimate.
        """

        if self.INDEX_PGA is None:
            return NotImplementedError
        else:
            return self._ln_std[self.INDEX_PGA]

    @property
    def pgv(self):
        """Peak ground velocity (PGV) computed by the model (cm/sec).

        Returns:
            :class:`float`

        Raises:
            NotImplementedError
                If model does not provide an estimate.
        """
        if self.INDEX_PGV is None:
            return NotImplementedError
        else:
            return self._resp(self.INDEX_PGV) * self.PGV_SCALE

    @property
    def ln_std_pgv(self):
        """Logarithmic standard deviation (:math:`\\sigma_{ \\ln}`) of the
        peak ground velocity computed by the model.

        Returns:
            :class:`float`

        Raises:
            NotImplementedError
                If model does not provide an estimate.
        """
        if self.INDEX_PGV is None:
            return NotImplementedError
        else:
            return self._ln_std[self.INDEX_PGV]

    @property
    def pgd(self):
        """Peak ground displacement (PGD) computed by the model (cm).

        Returns:
            :class:`float`

        Raises:
            NotImplementedError
                If model does not provide an estimate.
        """
        if self.INDEX_PGD is None:
            return NotImplementedError
        else:
            return self._resp(self.INDEX_PGD) * self.PGD_SCALE

    @property
    def ln_std_pgd(self):
        """Logarithmic standard deviation (:math:`\\sigma_{ \\ln}`) of the
        peak ground displacement computed by the model.

        Returns:
            :class:`float`

        Raises:
            NotImplementedError
                If model does not provide an estimate.
        """

        if self.INDEX_PGD is None:
            return NotImplementedError
        else:
            return self._ln_std[self.INDEX_PGD]

    def _resp(self, index):
        if index is not None:
            return np.exp(self._ln_resp[index])

    def _check_inputs(self):
        for p in self.PARAMS:
            self.params[p.name] = p.check(self.params.get(p.name, None))


class Parameter(object):
    def __init__(self, name, required=False, default=None):
        super(Parameter, self).__init__()

        self._name = name
        self._required = required
        self._default = default

    def check(self, value):
        raise NotImplementedError

    @property
    def default(self):
        return self._default

    @property
    def name(self):
        return self._name

    @property
    def required(self):
        return self._required


class NumericParameter(Parameter):
    def __init__(self, name, required=False, min=None, max=None, default=None):
        super(NumericParameter, self).__init__(name, required, default)
        self._min = min
        self._max = max

    @property
    def min(self):
        return self._min

    @property
    def max(self):
        return self._max

    def check(self, value):
        if value is None and self.required:
            raise ValueError(self.name, 'is a required parameter')

        if value is None:
            value = self.default
        else:
            if self.min is not None and value < self.min:
                logging.warning(
                    '{} ({:g}) is less than the recommended limit ({:g}).'.
                        format(self.name, value, self.min))
            elif self.max is not None and self.max < value:
                logging.warning(
                    '{} ({:g}) is greater than the recommended limit ({:g}).'.
                        format(self.name, value, self.max))

        return value


class CategoricalParameter(Parameter):
    def __init__(self, name, required=False, options=None, default=''):
        super(CategoricalParameter, self).__init__(name, required, default)
        self._options = options or []

    @property
    def options(self):
        return self._options

    def check(self, value):
        if value is None and self.required:
            raise ValueError(self.name, 'is a required parameter')

        if value is None:
            value = self.default
        elif value not in self.options:
            alert = logging.error if self._required else logging.warning
            alert(
                '{} value of "{}" is not one of the options. The following'
                ' options are possible: {}'
                    .format(self._name, value,
                            ', '.join([str(o) for o in self._options]))
            )

        return value


def load_data_file(name, skip_header=None):
    fname = os.path.join(os.path.dirname(__file__), 'data', name)
    return np.recfromcsv(fname, skip_header=skip_header).view(np.recarray)