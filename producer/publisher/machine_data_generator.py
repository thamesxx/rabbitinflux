"""
machine_data_generator.py

Synthetic generator for industrial PLC + utility telemetry.
MongoDB has been removed — use generate_one() to stream readings one at a time.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


# -----------------------------
# Helpers
# -----------------------------

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def seconds_to_hms(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}:{minutes}:{secs}"


def fmt_speed(value: float) -> str:
    return "0" if value <= 0 else f"{value:.2f}"


def fmt_length(value: float) -> str:
    return f"{value:.2f}"


def fmt_three(value: float) -> str:
    return f"{value:.3f}"


def fmt_floatish(value: float) -> str:
    return str(float(value))


# -----------------------------
# Profiles
# -----------------------------

@dataclass
class ArticleProfile:
    article: int
    nominal_speed: float = 25.0
    length_per_second: float = 0.422
    steam_flow_base: float = 2.8
    water_flow_base: float = 12.2
    steam_flow_noise: float = 0.35
    water_flow_noise: float = 0.18
    length_noise: float = 0.008
    steam_total_factor: float = 0.00025
    water_total_factor: float = 0.00042
    steam_phase_shift: float = 0.55
    water_phase_shift: float = 0.35


DEFAULT_PROFILE = ArticleProfile(article=5896)


# -----------------------------
# Generator
# -----------------------------

class SyntheticMachineGenerator:
    def __init__(
        self,
        seed: Optional[int] = None,
        profile: ArticleProfile = DEFAULT_PROFILE,
        machine_time_start_sec: Optional[int] = None,
        steam_total_start: Optional[float] = None,
        water_total_start: Optional[float] = None,
    ) -> None:
        self.rng = random.Random(seed)
        self.profile = profile

        self.machine_time_sec = (
            machine_time_start_sec
            if machine_time_start_sec is not None
            else self.rng.randint(7050 * 3600, 7090 * 3600)
        )

        self.steam_total = (
            steam_total_start
            if steam_total_start is not None
            else 39109.0 + self.rng.uniform(0.0, 1.0)
        )
        self.water_total = (
            water_total_start
            if water_total_start is not None
            else 171475.0 + self.rng.uniform(0.0, 1.0)
        )

        # Session state
        self.session_id: str = str(uuid.uuid4())
        self.lot_1, self.lot_2 = self._new_lot_ids()
        self.length: float = 0.0
        self.lot_time_sec: int = 0
        self.seq: int = 0
        self.phase = self._new_phase()
        self.phase_remaining: int = int(self.phase["duration"])

    def _new_lot_ids(self) -> Tuple[int, int]:
        lot_1 = self.rng.randint(2_000_000, 2_999_999)
        return lot_1, lot_1 + 1

    def _new_phase(self) -> Dict:
        p = self.profile
        steam_shift = self.rng.uniform(-p.steam_phase_shift, p.steam_phase_shift)
        water_shift = self.rng.uniform(-p.water_phase_shift, p.water_phase_shift)
        return {
            "steam_setpoint": clamp(p.steam_flow_base + steam_shift, 0.45, 4.0),
            "water_setpoint": clamp(p.water_flow_base + water_shift, 8.5, 13.5),
            "duration": self.rng.randint(8, 28),
        }

    def generate_one(self) -> Dict:
        """Generate and return a single reading, advancing internal state."""
        p = self.profile

        if self.phase_remaining <= 0:
            self.phase = self._new_phase()
            self.phase_remaining = int(self.phase["duration"])

        speed = p.nominal_speed

        length_increment = (
            p.length_per_second + self.rng.uniform(-p.length_noise, p.length_noise)
        ) * (speed / p.nominal_speed)
        self.length = max(self.length, 0.0) + max(0.001, length_increment)

        sf_flow = clamp(
            self.phase["steam_setpoint"] + self.rng.uniform(-p.steam_flow_noise, p.steam_flow_noise),
            0.10, 5.00,
        )
        wat_flow = clamp(
            self.phase["water_setpoint"] + self.rng.uniform(-p.water_flow_noise, p.water_flow_noise),
            6.50, 15.00,
        )

        self.steam_total += sf_flow * p.steam_total_factor
        self.water_total += wat_flow * p.water_total_factor
        self.machine_time_sec += 1

        reading = {
            "session_id": self.session_id,
            "seq": self.seq,
            "state": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plc": {
                "lot_1": self.lot_1,
                "lot_2": self.lot_2,
                "speed": fmt_speed(speed),
                "length": fmt_length(self.length),
                "article": p.article,
                "runmemory": True,
                "lot_time": seconds_to_hms(self.lot_time_sec),
                "machine_time": seconds_to_hms(self.machine_time_sec),
                "steam_consumed_lot": "0.00",
                "water_consumed_lot": "0.00",
                "power_consumed_lot": 0,
                "air_consumed_lot": 0,
            },
            "utility": {
                "SF_Flow": fmt_floatish(sf_flow),
                "SF_Tot": fmt_three(self.steam_total),
                "Wat_Flow": fmt_floatish(wat_flow),
                "Wat_Tot": fmt_three(self.water_total),
                "EM_Power": None,
                "EM_Energy": None,
            },
        }

        self.seq += 1
        self.lot_time_sec += 1
        self.phase_remaining -= 1

        return reading