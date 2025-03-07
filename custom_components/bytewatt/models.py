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
        """Create a BatterySettings instance from an API response."""
        settings = cls(
            grid_charge=data.get("grid_charge", 1),
            ctr_dis=data.get("ctr_dis", 1),
            bat_use_cap=data.get("bat_use_cap", 6),
            time_chaf1a=data.get("time_chaf1a", "14:30"),
            time_chae1a=data.get("time_chae1a", "16:00"),
            time_chaf2a=data.get("time_chaf2a", "00:00"),
            time_chae2a=data.get("time_chae2a", "00:00"),
            time_disf1a=data.get("time_disf1a", "16:00"),
            time_dise1a=data.get("time_dise1a", "23:00"),
            time_disf2a=data.get("time_disf2a", "06:00"),
            time_dise2a=data.get("time_dise2a", "10:00"),
            bat_high_cap=data.get("bat_high_cap", 100),
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
        )
        
        # Store additional fields
        additional_fields = {}
        for field in [
            "sys_sn", "ems_version", "charge_workdays", "bakbox_ver",
            "charge_weekend", "grid_Charge_we", "bat_highcap_we",
            "ctr_dis_we", "bat_usecap_we", "basic_mode_jp", "peace_mode_jp",
            "vpp_mode_jp", "channel1", "control_mode1", "start_time1a", 
            "end_time1a", "start_time1b", "end_time1b", "date1", 
            "charge_soc1", "ups1", "switch_on1", "switch_off1", 
            "delay1", "duration1", "pause1", "channel2", "control_mode2", 
            "start_time2a", "end_time2a", "start_time2b", "end_time2b", 
            "date2", "charge_soc2", "ups2", "switch_on2", "switch_off2", 
            "delay2", "duration2", "pause2", "l1_priority", "l2_priority", 
            "l3_priority", "l1_soc_limit", "l2_soc_limit", "l3_soc_limit", 
            "charge_mode2", "charge_mode1", "backupbox", "minv", "mbat", 
            "generator", "gc_output_mode", "generator_mode", "gc_soc_start", 
            "gc_soc_end", "gc_time_start", "gc_time_end", "gc_charge_power", 
            "gc_rated_power", "dg_cap", "dg_frequency", "gc_rate_percent", 
            "chargingpile", "currentsetting", "chargingmode", "charging_pile_list", 
            "chargingpile_control_open", "peak_fill_en", "peakvalue", "fillvalue", 
            "delta", "pm_offset", "pm_max", "pm_offset_en", "stoinv_type", 
            "loadcut_soc", "loadtied_soc", "ac_tied", "soc_50_flag", 
            "auto_soccalib_en", "three_unbalance_en", "enable_current_set", 
            "enable_obc_set", "upsReserve", "columnIsSow", "nmi", "state", 
            "agent", "country_code", "register_dynamic_export", "register_type"
        ]:
            if field in data:
                additional_fields[field] = data[field]
        
        settings.additional_fields = additional_fields
        return settings
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for API submissions."""
        result = {
            "grid_charge": self.grid_charge,
            "ctr_dis": self.ctr_dis,
            "bat_use_cap": self.bat_use_cap,
            "time_chaf1a": self.time_chaf1a,
            "time_chae1a": self.time_chae1a,
            "time_chaf2a": self.time_chaf2a,
            "time_chae2a": self.time_chae2a,
            "time_disf1a": self.time_disf1a,
            "time_dise1a": self.time_dise1a,
            "time_disf2a": self.time_disf2a,
            "time_dise2a": self.time_dise2a,
            "bat_high_cap": self.bat_high_cap,
            "time_cha_fwe1a": self.time_cha_fwe1a,
            "time_cha_ewe1a": self.time_cha_ewe1a,
            "time_cha_fwe2a": self.time_cha_fwe2a,
            "time_cha_ewe2a": self.time_cha_ewe2a,
            "time_dis_fwe1a": self.time_dis_fwe1a,
            "time_dis_ewe1a": self.time_dis_ewe1a,
            "time_dis_fwe2a": self.time_dis_fwe2a,
            "time_dis_ewe2a": self.time_dis_ewe2a,
            "peak_s1a": self.peak_s1a,
            "peak_e1a": self.peak_e1a,
            "peak_s2a": self.peak_s2a,
            "peak_e2a": self.peak_e2a,
            "fill_s1a": self.fill_s1a,
            "fill_e1a": self.fill_e1a,
            "fill_s2a": self.fill_s2a,
            "fill_e2a": self.fill_e2a,
            "pm_offset_s1a": self.pm_offset_s1a,
            "pm_offset_e1a": self.pm_offset_e1a,
            "pm_offset_s2a": self.pm_offset_s2a,
            "pm_offset_e2a": self.pm_offset_e2a,
        }
        
        # Add additional fields
        result.update(self.additional_fields)
        
        return result