"""Data models for the Byte-Watt integration."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class SoCData:
    """Represents battery State of Charge data."""

    soc: float = 0
    grid_consumption: float = 0
    battery: float = 0
    house_consumption: float = 0
    create_time: str = ""
    pv: float = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "SoCData":
        """Create a SoCData instance from an API response."""
        return cls(
            soc=data.get("soc", 0),
            grid_consumption=data.get("gridConsumption", 0),
            battery=data.get("battery", 0),
            house_consumption=data.get("houseConsumption", 0),
            create_time=data.get("createTime", ""),
            pv=data.get("pv", 0),
        )


@dataclass
class GridData:
    """Represents grid energy data."""

    total_solar_generation: float = 0
    total_feed_in: float = 0
    total_battery_charge: float = 0
    total_battery_discharge: float = 0
    pv_power_house: float = 0
    pv_charging_battery: float = 0
    total_house_consumption: float = 0
    grid_based_battery_charge: float = 0
    grid_power_consumption: float = 0

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "GridData":
        """Create a GridData instance from an API response."""
        return cls(
            total_solar_generation=data.get("Total_Solar_Generation", 0),
            total_feed_in=data.get("Total_Feed_In", 0),
            total_battery_charge=data.get("Total_Battery_Charge", 0),
            total_battery_discharge=data.get("Total_Battery_Discharge", 0),
            pv_power_house=data.get("PV_Power_House", 0),
            pv_charging_battery=data.get("PV_Charging_Battery", 0),
            total_house_consumption=data.get("Total_House_Consumption", 0),
            grid_based_battery_charge=data.get("Grid_Based_Battery_Charge", 0),
            grid_power_consumption=data.get("Grid_Power_Consumption", 0),
        )


@dataclass
class BatterySettings:
    """Represents battery settings."""

    grid_charge: int = 1
    ctr_dis: int = 1
    bat_use_cap: int = 6  # Minimum remaining SOC
    time_chaf1a: str = "14:30"  # Charge start time
    time_chae1a: str = "16:00"  # Charge end time
    time_chaf2a: str = "00:00"
    time_chae2a: str = "00:00"
    time_disf1a: str = "16:00"  # Discharge start time
    time_dise1a: str = "23:00"  # Discharge end time
    time_disf2a: str = "06:00"
    time_dise2a: str = "10:00"
    bat_high_cap: str = "100"
    ups_reserve_enable: bool = False
    last_updated: Optional[str] = None

    # Weekend settings
    time_cha_fwe1a: str = "00:00"
    time_cha_ewe1a: str = "00:00"
    time_cha_fwe2a: str = "00:00"
    time_cha_ewe2a: str = "00:00"
    time_dis_fwe1a: str = "00:00"
    time_dis_ewe1a: str = "00:00"
    time_dis_fwe2a: str = "00:00"
    time_dis_ewe2a: str = "00:00"

    # Peak settings
    peak_s1a: str = "00:00"
    peak_e1a: str = "00:00"
    peak_s2a: str = "00:00"
    peak_e2a: str = "00:00"

    # Fill settings
    fill_s1a: str = "00:00"
    fill_e1a: str = "00:00"
    fill_s2a: str = "00:00"
    fill_e2a: str = "00:00"

    # Offset settings
    pm_offset_s1a: str = "00:00"
    pm_offset_e1a: str = "00:00"
    pm_offset_s2a: str = "00:00"
    pm_offset_e2a: str = "00:00"

    # Additional fields
    additional_fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "BatterySettings":
        """Create a BatterySettings instance from the new API response."""
        settings = cls(
            grid_charge=data.get("gridCharge", 1),
            ctr_dis=data.get("ctrDis", 1),
            bat_use_cap=int(data.get("batUseCap", 6)),
            time_chaf1a=data.get("timeChaf1", "14:30"),
            time_chae1a=data.get("timeChae1", "16:00"),
            time_chaf2a=data.get("timeChaf2", "00:00"),
            time_chae2a=data.get("timeChae2", "00:00"),
            time_disf1a=data.get("timeDisf1", "16:00"),
            time_dise1a=data.get("timeDise1", "23:00"),
            time_disf2a=data.get("timeDisf2", "06:00"),
            time_dise2a=data.get("timeDise2", "10:00"),
            bat_high_cap=str(data.get("batHighCap", 100)),
            time_cha_fwe1a=data.get("time_cha_fwe1a", "00:00"),
            time_cha_ewe1a=data.get("time_cha_ewe1a", "00:00"),
            time_cha_fwe2a=data.get("time_cha_fwe2a", "00:00"),
            time_cha_ewe2a=data.get("time_cha_ewe2a", "00:00"),
            time_dis_fwe1a=data.get("time_dis_fwe1a", "00:00"),
            time_dis_ewe1a=data.get("time_dis_ewe1a", "00:00"),
            time_dis_fwe2a=data.get("time_dis_fwe2a", "00:00"),
            time_dis_ewe2a=data.get("time_dis_ewe2a", "00:00"),
            peak_s1a=data.get("peak_s1a", "00:00"),
            peak_e1a=data.get("peak_e1a", "00:00"),
            peak_s2a=data.get("peak_s2a", "00:00"),
            peak_e2a=data.get("peak_e2a", "00:00"),
            fill_s1a=data.get("fill_s1a", "00:00"),
            fill_e1a=data.get("fill_e1a", "00:00"),
            fill_s2a=data.get("fill_s2a", "00:00"),
            fill_e2a=data.get("fill_e2a", "00:00"),
            pm_offset_s1a=data.get("pm_offset_s1a", "00:00"),
            pm_offset_e1a=data.get("pm_offset_e1a", "00:00"),
            pm_offset_s2a=data.get("pm_offset_s2a", "00:00"),
            pm_offset_e2a=data.get("pm_offset_e2a", "00:00"),
            ups_reserve_enable=bool(int(data.get("upsReserve", 0))),
        )

        # Store additional fields
        additional_fields = {}
        for field in [
            "sys_sn",
            "ems_version",
            "charge_workdays",
            "bakbox_ver",
            "charge_weekend",
            "grid_Charge_we",
            "bat_highcap_we",
            "ctr_dis_we",
            "bat_usecap_we",
            "basic_mode_jp",
            "peace_mode_jp",
            "vpp_mode_jp",
            "channel1",
            "control_mode1",
            "start_time1a",
            "end_time1a",
            "start_time1b",
            "end_time1b",
            "date1",
            "charge_soc1",
            "ups1",
            "switch_on1",
            "switch_off1",
            "delay1",
            "duration1",
            "pause1",
            "channel2",
            "control_mode2",
            "start_time2a",
            "end_time2a",
            "start_time2b",
            "end_time2b",
            "date2",
            "charge_soc2",
            "ups2",
            "switch_on2",
            "switch_off2",
            "delay2",
            "duration2",
            "pause2",
            "l1_priority",
            "l2_priority",
            "l3_priority",
            "l1_soc_limit",
            "l2_soc_limit",
            "l3_soc_limit",
            "charge_mode2",
            "charge_mode1",
            "backupbox",
            "minv",
            "mbat",
            "generator",
            "gc_output_mode",
            "generator_mode",
            "gc_soc_start",
            "gc_soc_end",
            "gc_time_start",
            "gc_time_end",
            "gc_charge_power",
            "gc_rated_power",
            "dg_cap",
            "dg_frequency",
            "gc_rate_percent",
            "chargingpile",
            "currentsetting",
            "chargingmode",
            "charging_pile_list",
            "chargingpile_control_open",
            "peak_fill_en",
            "peakvalue",
            "fillvalue",
            "delta",
            "pm_offset",
            "pm_max",
            "pm_offset_en",
            "stoinv_type",
            "loadcut_soc",
            "loadtied_soc",
            "ac_tied",
            "soc_50_flag",
            "auto_soccalib_en",
            "three_unbalance_en",
            "enable_current_set",
            "enable_obc_set",
            "upsReserve",
            "columnIsSow",
            "nmi",
            "state",
            "agent",
            "country_code",
            "register_dynamic_export",
            "register_type",
        ]:
            if field in data:
                additional_fields[field] = data[field]

        settings.additional_fields = additional_fields
        return settings

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for API submissions using new API format."""
        result = {
            "id": "",  # Empty for all devices
            "basicModeJp": None,
            "peaceModeJp": None,
            "vppModeJp": None,
            "gridCharge": self.grid_charge,
            "timeChaf1": self.time_chaf1a,
            "timeChae1": self.time_chae1a,
            "timeChaf2": self.time_chaf2a,
            "timeChae2": self.time_chae2a,
            "ctrDis": self.ctr_dis,
            "timeDisf1": self.time_disf1a,
            "timeDise1": self.time_dise1a,
            "timeDisf2": self.time_disf2a,
            "timeDise2": self.time_dise2a,
            "batHighCap": (
                float(self.bat_high_cap)
                if isinstance(self.bat_high_cap, str)
                else self.bat_high_cap
            ),
            "batUseCap": self.bat_use_cap,
            "batCapRange": [0, 100],  # Default range
            "isJapaneseDevice": False,
            "upsReserveEnable": self.ups_reserve_enable,
            "upsReserve": 1 if self.ups_reserve_enable else 0,
            "mbat": "BW-BAT-10.1P",  # Default battery model
            "chargeModeSetting": 0,
            "loadcutoutEn": 0,
            "cutoffSoc": 0,
            "wakeupSoc": 0,
            "timeChaMode": 0,
            "hasBalconyModel": 0,
            "balconyModel": None,
            "timeExpLimW1": 800,
            "timeExpLimW2": 800,
            "isSiteDevice": None,
        }

        # Add additional fields
        result.update(self.additional_fields)

        return result


@dataclass
class FeedStrategySchedule:
    """Represents a single feed-in strategy schedule."""

    id: Optional[int] = None
    sys_sn: str = ""
    start: str = "00:00"
    end: str = "00:00"
    feed_power: float = 0.0
    sort: int = 1


@dataclass
class FeedStrategySettings:
    """Represents feed-in strategy settings from getFeedStrategyList."""

    battery_en: int = 0
    battery_feed_cutoff_soc: float = 0.0
    id: str = ""
    precharge_en: int = 0
    poinv: float = 5000.0
    feed_strategy_list: List[FeedStrategySchedule] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "FeedStrategySettings":
        """Create a FeedStrategySettings instance from API response.

        We default feedPower to 0 and start/end time to "00:00" if
        schedules are empty or don't cover the required sorts.
        """
        vo_list = data.get("feedStrategyVOList") or []
        schedules = []
        for vo in vo_list:
            schedules.append(
                FeedStrategySchedule(
                    id=vo.get("id"),
                    sys_sn=vo.get("sysSn", ""),
                    start=vo.get("start", "00:00"),
                    end=vo.get("end", "00:00"),
                    feed_power=float(vo.get("feedPower", 0.0)),
                    sort=int(vo.get("sort", 1)),
                )
            )

        # Ensure sort 1 and sort 2 are ALWAYS in the list!
        has_sort_1 = any(s.sort == 1 for s in schedules)
        has_sort_2 = any(s.sort == 2 for s in schedules)

        sys_sn = ""
        if vo_list:
            sys_sn = vo_list[0].get("sysSn", "")

        if not has_sort_1:
            schedules.append(
                FeedStrategySchedule(
                    id=None,
                    sys_sn=sys_sn,
                    start="00:00",
                    end="00:00",
                    feed_power=0.0,
                    sort=1,
                )
            )
        if not has_sort_2:
            schedules.append(
                FeedStrategySchedule(
                    id=None,
                    sys_sn=sys_sn,
                    start="00:00",
                    end="00:00",
                    feed_power=0.0,
                    sort=2,
                )
            )

        # Keep the list sorted for predictable payloads and comparisons
        schedules.sort(key=lambda s: s.sort)

        return cls(
            battery_en=data.get("batteryEn", 0),
            battery_feed_cutoff_soc=float(data.get("batteryFeedCutoffSoc", 0.0)),
            id=data.get("id", ""),
            precharge_en=data.get("prechargeEn", 0),
            poinv=float(data.get("poinv", 5000.0)),
            feed_strategy_list=schedules,
        )

    def get_schedule_by_sort(self, sort_order: int) -> FeedStrategySchedule:
        """Get a schedule by sort order or return a default empty schedule.

        Ensures we default to 0 for feedPower, "00:00" for start and end times.
        """
        for sched in self.feed_strategy_list:
            if sched.sort == sort_order:
                return sched
        return FeedStrategySchedule(start="00:00", end="00:00", feed_power=0.0, sort=sort_order)
