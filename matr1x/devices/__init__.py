# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import logging

from .boss import BOSS  # noqa: F401
from .cryogenics import CryogenicBipolarPS, CryogenicPS  # noqa: F401
from .cryomagnetics import CS04  # noqa: F401
from .cryovac import TIC500  # noqa: F401
from .danfysik import Danfysik9100, Danfysik9700  # noqa: F401
from .hp import HP3245A  # noqa: F401
from .keithley import (  # noqa: F401
    Keithley2000,
    Keithley2182A,
    Keithley2400,
    Keithley2450,
    Keithley2611A,
    Keithley2701,
    Keithley6221,
    KeithleyDMM6500,
)
from .kepco import BOP5020mg  # noqa: F401
from .keysight import (  # noqa: F401
    PSA_E4440A,
    PSG8257D,
    KeysightB2961,
    PNA5225b,
    Agilent8114A,
)
from .lakeshore import Lakeshore335, Lakeshore340, Lakeshore475  # noqa: F401
from .magnet_physik import FH55  # noqa: F401
from .minicircuits import RC_2SPDT_A18  # noqa: F401
from .nanotec import NanotecPD4  # noqa: F401
from .owis import SMS, Ps10  # noqa: F401
from .oxford import ILM200, IPS120, ITC503, IPS120_switchheater  # noqa: F401
from .oxford_mercury import (MercuryIPS, MercuryITC,  # noqa: F401
                             MercurySingleAxisIPS)
from .pfeiffer import MPT200  # noqa: F401
from .physikinstrumente import MercuryC663  # noqa: F401
from .pico import PicoVNA  # noqa: F401
from .rohdeschwarz import FSW8  # noqa: F401
from .standa import Standa8SMC1  # noqa: F401
from .stanford_research_systems import SR830  # noqa: F401
from .thorlabs import BSC103  # noqa: F401
from .twickenham import HDI  # noqa: F401
from .visadevice import VisaDevice  # noqa: F401

logger = logging.getLogger(__name__)
logger.info("Device library imported")
scpiPORTdrivers = 8888