"""
Copyright Andrew Fernie, 2025

log_processor.py

Provides classes and functions for loading, parsing, processing, and exporting RC flight log data
in CSV format, metadata extraction, channel access, and summary statistics.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from pyproj import Proj
from pymavlink import mavutil


class LogData:
    """
    Container for raw and processed log data, metadata, and file information.
    """

    def __init__(self):
        """
        Initialize LogData with empty attributes.
        """
        self.raw_data: List[Dict[str, Any]] = []
        self.processed_data: Optional[pd.DataFrame] = None
        self.channels: List[str] = []
        self.sample_rate: float = 0.0
        self.duration: float = 0.0
        self.metadata: Dict[str, Any] = {}
        self.file_path: Optional[Path] = None
        self.log_file_type: Optional[str] = None
        self.user_home_position: Optional[Tuple[float, float, float]] = None


class LogProcessor:
    """
    Main class for loading, parsing, processing, and exporting RC flight log data in a CSV file.

    Initialize LogProcessor with no loaded log and supported formats.
    """

    def __init__(self):
        self.current_log: Optional[LogData] = None
        self.supported_formats = ['.csv', '.tlog', '.bin']
        self.imported_message_types = []

    def load_file(self, file_path: str, config: Dict[str, Any], progress_callback=None) -> bool:
        """
        Load a log file in CSV format and parse its contents.

        Args:
            file_path (str): Path to the log file.

        Returns:
            bool: True if file loaded and parsed successfully, False otherwise.
        """

        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            if path.suffix.lower() not in self.supported_formats:
                raise ValueError(f"Unsupported file format: {path.suffix}")

            self.current_log = LogData()
            self.current_log.file_path = path
            self.file_type = path.suffix.lower()

            # The argument "config" is an object imported from a json file that contains the
            # configuration for the log processing. It is used to map the CSV columns to their
            # respective channels.

            # Parse the file based on format
            if path.suffix.lower() == '.csv':
                # retrieve the section of config_string related to CSV
                csv_config = config["csv_file"]
                success = self._parse_csv_file(
                    path, csv_config, progress_callback)
            elif path.suffix.lower() == '.tlog':
                tlog_config = config["tlog_file"]
                success = self._parse_tlog_file(
                    path, tlog_config, progress_callback)
            elif path.suffix.lower() == '.bin':
                bin_config = config["bin_file"]
                success = self._parse_bin_file(
                    path, bin_config, progress_callback)
            else:
                success = False

            if success and self.current_log.processed_data is not None:
                self._extract_metadata()
                return True

            return False

        except Exception as e:
            print(f"Error loading file: {e}")
            return False

    def set_home_position(self, lat, lng, alt):
        """
        Slot to receive home position updates from MainWindow.
        Args:
            lat (float): Latitude of new home position.
            lng (float): Longitude of new home position.
            alt (float): Altitude of new home position.
        """
        # Save the new home position.
        self.current_log.user_home_position = (lat, lng, alt)

        # Recompute GPS derived data if we have GPS data
        df = self.generate_gps_derived_data(self.current_log.processed_data)
        self.current_log.processed_data = df
        self.current_log.channels = list(df.columns)

    def _parse_csv_file(self, file_path: Path, config: Dict[str, Any], progress_callback=None) -> bool:
        """
        Parse a CSV log file and process its contents. This supports both FrSky Ethos
        and OpenTX log files, along with limited support for generic CSV files.
        1. If an Ethos file is selected then related channels are automatically grouped.
        2. Limited grouping is performed for OpenTX files.
        3. Generic CSV files may not contain a data series with timestamps. In this case,
           the application will assume a 1 second interval between samples. This is likely
           to result in inaccurate timestamps, but at least allows the data to be imported
           and plotted.

        Args:
            file_path (Path): Path to the CSV file.

        Returns:
            bool: True if parsing was successful, False otherwise.
        """

        try:
            import_status = ""
            # Read CSV file
            percent_complete = 0
            if progress_callback:
                progress_callback(percent_complete)
            df = pd.read_csv(file_path, on_bad_lines='skip')

            percent_complete = 100
            if progress_callback:
                progress_callback(percent_complete)

            # Basic validation
            if df.empty:
                return False

            self.current_log.log_file_type = "csv"

            # Remove empty columns
            df = df.dropna(axis=1, how='all')

            lat_col = None
            lon_col = None

            # Split GPS column if present
            if 'GPS' in df.columns:
                import_status += "Contains GPS data.\n"
                gps_split = df['GPS'].str.split(' ', expand=True)

                # For each row in gps_split, if either gps_split[0] or gps_split[1] is equal to '0.000000',
                # set both to NaN. This catches some cases of bad data, and it is unlikely that the
                # GPS receiver would report a valid latitude or longitude with a value of exactly '0.000000'

                gps_valid = ~((gps_split[0] == '0.000000') | (gps_split[1] == '0.000000'))
                gps_split = gps_split.where(gps_valid, np.nan)
                            # Find a column in df that starts with 'GPS.Latitude'
                lat_col = 'GPS.Latitude'
                lon_col = 'GPS.Longitude'

                df[lat_col] = gps_split[0]
                df[lon_col] = gps_split[1]
                df = df.drop(columns=['GPS'])

            else:
                import_status += "No GPS data found.\n"

            # The files from the radio should have Date and Time columns, and this application
            # will combine them into a DateTime column for more convenient processing. However,
            # if the file being opened is one that was previously processed and exported from
            # this application then the DateTime column will already exist, and there is no need
            # to regenerate it.
            if not 'DateTime' in df.columns:
                # There was no DateTime column, so we need to create one. If either Date or
                # Time is missing, we will generate one. The generated data won't be accurate,
                # but at least it allows the various data series to be plotted.
                if 'Time' in df.columns:
                    # Ensure 'Time' is in HH:MM:SS.f format (with one or more "f" digits). The
                    # typical problem is that if the file has gone through Excel and HH should
                    # have been '12' it may have been dropped and we only have MM:SS.f format
                    # with an implied '12:' at the front. If so, we prepend '12:' to the time.
                    if not re.match(r'^\d{1,2}:\d{2}:\d{2}\.\d+$', df['Time'].iloc[0]):
                        print(
                            "Warning: 'Time' column format is not HH:MM:SS.f. Prepending '12:' "
                            "to the time values.")
                        df['Time'] = '12:' + df['Time'].astype(str)
                else:
                    # If no Time column, generate one assuming start at 12:00:00 and 1 second
                    # between each sample
                    start_time = datetime.strptime("12:00:00.0", "%H:%M:%S.%f")
                    df['Time'] = [(start_time + pd.Timedelta(seconds=i)
                                   ).strftime("%H:%M:%S.%f")[:-3] for i in range(len(df))]
                    print("Warning: 'Time' column not found. Using generated time values starting"
                          " at 12:00:00.0 with 1 second intervals.")
                    import_status += "No time data found.\n"

                if not 'Date' in df.columns:
                    # If only Time is present, use current date
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    print(
                        f"Warning: 'Date' column not found. Using current date: {current_date}")
                    df['Date'] = current_date
                    import_status += "No date data found.\n"

                # At this point we should have both Date and Time columns, either from the file
                # or generated.
                df['DateTime'] = pd.to_datetime(df['Date'].astype(str) + ' ' +
                                                df['Time'].astype(str),
                                                errors='coerce')

                # Calculate ElapsedTime as an offset from the first DateTime
                if not df['DateTime'].isnull().all():
                    first_time = df['DateTime'].iloc[0]
                    df['ElapsedTime'] = (
                        df['DateTime'] - first_time).dt.total_seconds()
                else:
                    df['ElapsedTime'] = None

            # Map the DataFrame columns to their respective channels using the config
            # df = df.rename(columns=self.config.get("csv_file", {}).get("channel_mapping", {}))
            df = df.rename(columns=config.get("channel_mapping", {}))

            # Compute the custom data series if GPS data is present
            df = self.generate_gps_derived_data(df)

            # Compute LiPo Total (V) if any "LiPo<N> (V)"" columns exist
            lipo_cols = [col for col in df.columns if re.match(
                r"POWER.LiPo\d+ \(V\)", col)]

            if lipo_cols:
                df['POWER.LiPo.Total (V)'] = df[lipo_cols].sum(axis=1)
                import_status += "Generated 'LiPo.Total (V)' data.\n"

            # Compute Power(W) if VFAS(V) and Current(A) are present
            if 'POWER.VFAS (V)' in df.columns and 'POWER.Current (A)' in df.columns:
                df['POWER.Power (W)'] = self._compute_power(df, 'POWER.VFAS (V)', 'POWER.Current (A)')
                import_status += "Generated 'Power (W)' data.\n"

            # Sort columns alphabetically
            df = df[sorted(df.columns)]

            # Store processed data
            self.current_log.processed_data = df
            self.current_log.channels = list(df.columns)

            # We don't have any messages in a basic csv file
            self.imported_message_types = []
            self.nonimported_message_types = []

            return True

        except Exception as e:
            print(f"Error parsing CSV file: {e}")
            self.current_log.log_file_type = None
            return False

    def _parse_tlog_file(self, file_path: Path, config: Dict[str, Any], progress_callback=None) -> bool:
        """
        Parse a MAVLink .tlog file and process its contents into a pandas DataFrame.

        Args:
            file_path (Path): Path to the tlog file.
            progress_callback (callable, optional): Function to call with percent_complete (0-100).

        Returns:
            bool: True if parsing was successful, False otherwise.
        """
        import_status = ""

        try:
            # Open the tlog file using pymavlink
            mlog = mavutil.mavlink_connection(str(file_path))
            data = []
            imported_message_types = []
            nonimported_message_types = []

            # TLOG files are essentially records of MAVLINK messages.
            # See https://mavlink.io/en/messages/common.html for message definitions.
            #
            # They can include time series data as well as one-time parameters, file transfers, etc.
            # We are concerned primarily with time series data, and even for time series data, the
            # content of the TLOG file will depend on the specific MAVLink messages being sent and
            # received. So, we need to define the message types we are interested in, and this is
            # done in the config file through an object "selected_messages".
            desired_msg_types = list(config.get("selected_messages", {}).keys())

            # Retrieve the scaling dictionary for unit conversions from the config file. The names
            # are those found in the pymavlink message fieldunits_by_name attribute.
            scaling_dict = config.get("scaling", {})

            # Iterate through all messages in the log file
            while True:
                # msg = mlog.recv_match(type=desired_msg_types, blocking=False)
                msg = mlog.recv_match(blocking=False)

                if msg is None:
                    break

                if msg.get_type() in desired_msg_types:

                    # Track the message types present in the file but not imported

                    if msg.get_type() not in imported_message_types:
                        imported_message_types.append(msg.get_type())

                    percent_complete = mlog.percent
                    if progress_callback:
                        progress_callback(percent_complete)

                    msg_datetime = pd.to_datetime(datetime.fromtimestamp(msg._timestamp
                                                                        ).strftime('%Y-%m-%d %H:%M:%S.%f'))

                    msg_dict = msg.to_dict()

                    # Get the "group" to which each parameter is assigned, and to be used as the prefix to the DataFrame column.
                    msg_group = config.get("selected_messages", {}).get(
                        msg.get_type(), {}).get("group", "UNKNOWN")

                    # Get the timestamp for this message and make it the first entry in the data_list
                    data_list = {'DateTime': msg_datetime}

                    # Check the field "all_channels", which indicates that all channels found in the message
                    # should be imported.
                    all_channels = config.get("selected_messages", {}).get(
                        msg.get_type(), {}).get("all_channels", 0)

                    fieldnames = msg.get_fieldnames()
                    num_fields = len(fieldnames)

                    # Find the fields listed in the config file we said we are interested in
                    config_msg_fields = config.get("selected_messages", {}).get(
                        msg.get_type(), {}).get("channel", {})

                    # Get the units for each field (channel) in the message
                    msg_units = msg.fieldunits_by_name

                    for i in range(num_fields):
                        field_name = fieldnames[i]

                        # Don't bother with any field name starting with "time_" - we already have the message
                        # timestamp.
                        if (not field_name.startswith("time_") and
                            (all_channels > 0 or field_name in config_msg_fields)):
                            field_info = msg_dict.get(field_name, {})
                            field_units = msg_units.get(field_name, None)
                            this_config_msg_field = config_msg_fields.get(field_name, {})

                            if this_config_msg_field is not None:
                                base_name = this_config_msg_field.get("base_name", field_name)
                            else:
                                base_name = field_name

                            if field_units is not None:
                                scaling_info = scaling_dict.get(field_units, None)
                            else:
                                scaling_info = None

                            if scaling_info is not None:
                                field_units_suffix = scaling_info.get("units_suffix", "")
                            else:
                                field_units_suffix = ""

                            if field_units_suffix == "":
                                df_col_name = f"{msg_group}.{base_name}"
                            else:
                                df_col_name = f"{msg_group}.{base_name} ({field_units_suffix})"

                            if scaling_info is not None:
                                scale = scaling_info.get("scale", 1)
                            else:
                                scale = 1

                            if field_units is not None and isinstance(field_info, (int, float)):
                                df_col_value = field_info * scale
                            else:
                                df_col_value = field_info

                            data_list.update({df_col_name: df_col_value})

                    if len(data_list) > 1:
                        data.append(data_list)

                else:
                    # Track the message types present in the file but not imported
                    if msg.get_type() not in nonimported_message_types:
                        nonimported_message_types.append(msg.get_type())


            if not data:
                self.current_log.log_file_type = None
                return False

            self.current_log.log_file_type = "tlog"

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Fill in the missing values that result from only getting a subset of data values
            # in each message.
            df = df.ffill()

            # Calculate ElapsedTime as an offset from the first DateTime
            if not df['DateTime'].isnull().all():
                first_time = df['DateTime'].iloc[0]
                df['ElapsedTime'] = (
                    df['DateTime'] - first_time).dt.total_seconds()
            else:
                df['ElapsedTime'] = None


            # Find the name of the first columns in df that starts with 'GPS.Latitude'
            # or 'GPS.Longitude'
            lat_col = df.columns[df.columns.str.startswith('GPS.Latitude')][0] if any(
                df.columns.str.startswith('GPS.Latitude')) else None
            lon_col = df.columns[df.columns.str.startswith('GPS.Longitude')][0] if any(
                df.columns.str.startswith('GPS.Longitude')) else None

            if lon_col is not None and lat_col is not None:
                import_status += "Contains GPS data.\n"
                # Compute the custom data series if GPS data is present
                df = self.generate_gps_derived_data(df)

            else:
                import_status += "No GPS data found.\n"

            # Compute Power(W) if SYS.BatteryVoltage(V) and SYS.BatteryCurrent(A) are present
            if 'SYS.BatteryVoltage (V)' in df.columns and 'SYS.BatteryCurrent (A)' in df.columns:
                df['SYS.Power (W)'] = df['SYS.BatteryVoltage (V)'] * \
                    df['SYS.BatteryCurrent (A)']
                import_status += "Generated 'Power (W)' data.\n"

            # Sort columns alphabetically
            df = df[sorted(df.columns)]

            # Store processed data
            self.current_log.processed_data = df
            self.current_log.channels = list(df.columns)
            self.imported_message_types = imported_message_types
            self.nonimported_message_types = nonimported_message_types
            return True

        except Exception as e:
            print(f"Error parsing tlog file: {e}")
            self.current_log.log_file_type = None
            return False

    def _parse_bin_file(self, file_path: Path, config: Dict[str, Any], progress_callback=None) -> bool:
        """
        Parse an Ardupilot dataflash log (.bin) file and process its contents into a pandas DataFrame.

        Args:
            file_path (Path): Path to the .bin file.
            progress_callback (callable, optional): Function to call with percent_complete (0-100).

        Returns:
            bool: True if parsing was successful, False otherwise.
        """
        import_status = ""

        try:
            # Open the tlog file using pymavlink
            mlog = mavutil.mavlink_connection(str(file_path))
            data = []
            imported_message_types = []
            nonimported_message_types = []

            # Dataflash log (.bin) files can include time series data as well as one-time
            # parameters, etc.

            # Message definitions can be found here:
            # https://ardupilot.org/copter/docs/logmessages.html#logmessages
            # https://ardupilot.org/plane/docs/logmessages.html#logmessages

            # We are concerned primarily with time series data, and even
            # for time series data, the content of the bin will depend on how the flight
            # controller has been configured. So, we need to define the message types we
            # are interested in, and this is done in the config file through an object
            # "selected_messages".

            desired_msg_types = list(config.get(
                "selected_messages", {}).keys())

            # Retrieve the scaling dictionary for unit conversions from the config file. The names
            # are those found in the pymavlink message fieldunits_by_name attribute.
            scaling_dict = config.get("scaling", {})

            # Iterate through all messages in the log file
            while True:
                # msg = mlog.recv_match(type=desired_msg_types, blocking=False)
                msg = mlog.recv_match(blocking=False)

                if msg is None:
                    break

                if msg.get_type() in desired_msg_types:

                    # Track the message types present in the file but not imported
                    if msg.get_type() not in imported_message_types:
                        imported_message_types.append(msg.get_type())

                    percent_complete = mlog.percent
                    if progress_callback:
                        progress_callback(percent_complete)

                    # Get the timestamp for this message
                    msg_datetime = pd.to_datetime(datetime.fromtimestamp(msg._timestamp
                                                                        ).strftime('%Y-%m-%d %H:%M:%S.%f'))

                    msg_dict = msg.to_dict()

                    # Get the "group" to which each parameter is assigned, and to be used as the prefix to the DataFrame column.
                    msg_group = config.get("selected_messages", {}).get(
                        msg.get_type(), {}).get("group", "UNKNOWN")

                    # Get the timestamp for this message and make it the first entry in the data_list
                    data_list = {'DateTime': msg_datetime}

                    # Check the field "all_channels", which indicates that all channels found in the message
                    # should be imported.
                    all_channels = config.get("selected_messages", {}).get(
                        msg.get_type(), {}).get("all_channels", 0)

                    fieldnames = msg.get_fieldnames()
                    num_fields = len(fieldnames)

                    # Find the fields listed in the config file we said we are interested in
                    config_msg_fields = config.get("selected_messages", {}).get(
                        msg.get_type(), {}).get("channel", {})

                    # Get the units for each field (channel) in the message
                    msg_units = msg.fmt.units

                    for i in range(num_fields):
                        field_name = fieldnames[i]

                        # Don't bother with any field name starting with "TimeUS" - we already have the message
                        # timestamp.
                        if (not field_name.startswith("TimeUS") and
                            (all_channels > 0 or field_name in config_msg_fields)):
                            field_info = msg_dict.get(field_name, {})
                            field_units = msg_units[i]
                            this_config_msg_field = config_msg_fields.get(field_name, {})

                            if this_config_msg_field is not None:
                                base_name = this_config_msg_field.get("base_name", field_name)
                            else:
                                base_name = field_name

                            if field_units is not None:
                                scaling_info = scaling_dict.get(field_units, None)
                            else:
                                scaling_info = None

                            if scaling_info is not None:
                                field_units_suffix = scaling_info.get("units_suffix", "")
                            else:
                                field_units_suffix = ""

                            if field_units_suffix == "":
                                df_col_name = f"{msg_group}.{base_name}"
                            else:
                                df_col_name = f"{msg_group}.{base_name} ({field_units_suffix})"

                            if scaling_info is not None:
                                scale = scaling_info.get("scale", 1)
                            else:
                                scale = 1

                            if field_units is not None and isinstance(field_info, (int, float)):
                                df_col_value = field_info * scale
                            else:
                                df_col_value = field_info

                            data_list.update({df_col_name: df_col_value})


                    if len(data_list) > 1:
                        data.append(data_list)

                else:
                    # Track the message types present in the file but not imported
                    if msg.get_type() not in nonimported_message_types:
                        nonimported_message_types.append(msg.get_type())

            if not data:
                self.current_log.log_file_type = None
                return False

            self.current_log.log_file_type = "bin"

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Fill in the missing values that result from only getting a subset of data values
            # in each message.
            df = df.ffill()

            # Calculate ElapsedTime as an offset from the first DateTime
            if not df['DateTime'].isnull().all():
                first_time = df['DateTime'].iloc[0]
                df['ElapsedTime'] = (
                    df['DateTime'] - first_time).dt.total_seconds()
            else:
                df['ElapsedTime'] = None

            # Find the name of the first column in df that starts with 'GPS.Lat' or 'GPS.Lon'
            lat_col = df.columns[df.columns.str.startswith('GPS.Lat')][0] if any(
                df.columns.str.startswith('GPS.Lat')) else None
            lon_col = df.columns[df.columns.str.startswith('GPS.Lon')][0] if any(
                df.columns.str.startswith('GPS.Lon')) else None

            # Some longitude fields in dataflash logs start with "Lng" rather than "Lon"
            if lon_col is None:
                lon_col = df.columns[df.columns.str.startswith('GPS.Lng')][0] if any(
                    df.columns.str.startswith('GPS.Lng')) else None

            if lat_col is not None and lon_col is not None:
                import_status += "Contains GPS data.\n"
                # Compute the custom data series if GPS data is present
                df = self.generate_gps_derived_data(df)

            else:
                import_status += "No GPS data found.\n"

            # Sort columns alphabetically
            df = df[sorted(df.columns)]

            # Store processed data
            self.current_log.processed_data = df
            self.current_log.channels = list(df.columns)
            self.imported_message_types = sorted(imported_message_types)
            self.nonimported_message_types = sorted(nonimported_message_types)

            return True

        except Exception as e:
            print(f"Error parsing bin file: {e}")
            self.current_log.log_file_type = None
            return False

    def _compute_xy_excursions(self, df: pd.DataFrame,
                               lat_col: str, lon_col: str) -> Tuple[pd.Series, pd.Series]:
        """
        Compute X and Y excursions in meters from the center GPS point using pyproj.

        Args:
            df (pd.DataFrame): DataFrame containing GPS longitude and latitude columns.
            lon_col (str): Name of the longitude column.
            lat_col (str): Name of the latitude column.

        Returns:
            Tuple[pd.Series, pd.Series]: X and Y excursions in meters.
        """
        if lon_col in df.columns and lat_col in df.columns:
            # Compute X/Y excursions in meters from center GPS point if GPS columns exist
            # Convert to float in case they are strings
            lon_data_float = df[lon_col].astype(float)
            lat_data_float = df[lat_col].astype(float)
            lon0 = lon_data_float.mean()
            lat0 = lat_data_float.mean()

            # Use pyproj for accurate projection (WGS84)
            proj = Proj(proj='aeqd', lat_0=lat0, lon_0=lon0, datum='WGS84')
            x, y = proj(lon_data_float.values, lat_data_float.values)

            return x, y
        else:
            return pd.Series(dtype=float), pd.Series(dtype=float)

    def _compute_distance_from_target(self, df: pd.DataFrame, lat_col: str, lon_col: str, home_lat: float, home_lon: float) -> pd.Series:
        """
        Compute distance from home position using the Haversine formula.

        Args:
            df (pd.DataFrame): DataFrame containing latitude and longitude columns.
            lat_col (str): Name of the latitude data column.
            lon_col (str): Name of the longitude data column.
            home_lat_col (str): Name of the home latitude column.
            home_lon_col (str): Name of the home longitude column.

        Returns:
            pd.Series: Series containing distances from home position in meters.
        """
        # Haversine formula implementation
        R = 6371000  # Earth radius in meters
        lat1 = np.radians(home_lat)
        lon1 = np.radians(home_lon)
        lat_data_float = np.radians(df[lat_col].astype(float))
        lon_data_float = np.radians(df[lon_col].astype(float))

        dlat = lat_data_float - lat1
        dlon = lon_data_float - lon1

        a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat_data_float) * np.sin(dlon / 2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return R * c

    def _compute_bearing_to_target(self, df: pd.DataFrame, lat_col: str, lon_col: str, home_lat: float, home_lon: float) -> pd.Series:
        """
        Compute bearing to home position using the initial bearing formula.

        Args:
            df (pd.DataFrame): DataFrame containing latitude and longitude columns.
            home_lat_col (str): Name of the home latitude column.
            home_lon_col (str): Name of the home longitude column.

        Returns:
            pd.Series: Series containing bearings to home position in degrees.
        """
        # Initial bearing formula implementation
        lat1 = np.radians(home_lat)
        lon1 = np.radians(home_lon)
        lat_data_float = np.radians(df[lat_col].astype(float))
        lon_data_float = np.radians(df[lon_col].astype(float))

        dlon = lon_data_float - lon1

        x = np.sin(dlon) * np.cos(lat_data_float)
        y = np.cos(lat1) * np.sin(lat_data_float) - np.sin(lat1) * np.cos(lat_data_float) * np.cos(dlon)
        initial_bearing = np.arctan2(x, y)

        # Convert bearing from radians to degrees
        return np.degrees(initial_bearing)

    def _compute_elevation_to_target(self, df: pd.DataFrame, lat_col: str, lon_col: str, alt_col: str,
                                     home_lat: float, home_lon: float, home_alt: float) -> pd.Series:
        """
        Compute distance from home position using the Haversine formula.

        Args:
            df (pd.DataFrame): DataFrame containing latitude and longitude columns.
            lat_col (str): Name of the latitude data column.
            lon_col (str): Name of the longitude data column.
            alt_col (str): Name of the altitude data column.
            home_lat (float): Home latitude.
            home_lon (float): Home longitude.
            home_alt (float): Home altitude.

        Returns:
            pd.Series: Series containing elevation angles to home position in degrees.
        """
        # Haversine formula implementation
        R = 6371000  # Earth radius in meters
        lat1 = np.radians(home_lat)
        lon1 = np.radians(home_lon)
        if home_alt is None:
            alt1 = 0.0
        else:
            alt1 = home_alt

        lat_data_float = np.radians(df[lat_col].astype(float))
        lon_data_float = np.radians(df[lon_col].astype(float))
        alt_data_float = df[alt_col].astype(float)

        dlat = lat_data_float - lat1
        dlon = lon_data_float - lon1
        dalt = alt_data_float - alt1

        a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat_data_float) * np.sin(dlon / 2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        distance = R * c

        # Compute elevation angle
        elevation_angle = np.arctan2(dalt, distance)

        # Convert elevation angle from radians to degrees
        return np.degrees(elevation_angle)

    def _compute_power(self, df: pd.DataFrame, voltage_col: str, current_col: str) -> pd.Series:
        """
         Compute power in watts from voltage and current columns.

        Args:
            df (pd.DataFrame): DataFrame containing voltage and current columns.
            voltage_col (str): Name of the voltage column.
            current_col (str): Name of the current column.

        Returns:
            pd.Series: Series containing power values in watts.
        """
        if voltage_col in df.columns and current_col in df.columns:
            return df[voltage_col] * df[current_col]
        else:
            return pd.Series(dtype=float)

    # Method to find the first valid latitude and longitude in the provided columns
    def _find_initial_valid_gps_data(self, df: pd.DataFrame, lat_col: str, lon_col: str,
                                   alt_col: str) -> Tuple[float, float, float]:
        """
        Find the initial valid latitude and longitude in the provided columns.

        Args:
            df (pd.DataFrame): DataFrame containing latitude and longitude columns.
            lat_col (str): Name of the latitude column.
            lon_col (str): Name of the longitude column.
            alt_col (str): Name of the altitude column.

        Returns:
            Tuple[float, float, float]: First valid latitude, longitude, and altitude values.
        """

        # Find the 10th not null valid latitude and longitude in the provided columns. We use the
        # 10th valid value to avoid any initial bad data that might be present.
        valid_lat = df[lat_col].notnull()
        valid_lon = df[lon_col].notnull()
        valid_alt = df[alt_col].notnull()
        valid_indices = df[valid_lat & valid_lon & valid_alt].index

        if len(valid_indices) >= 10:
            # Get the 10th valid index
            tenth_valid_index = valid_indices[9]
            lat_f = float(df.at[tenth_valid_index, lat_col])
            lon_f = float(df.at[tenth_valid_index, lon_col])
            alt_f = float(df.at[tenth_valid_index, alt_col])

        else:
            # Not enough valid data
            lat_f = None
            lon_f = None
            alt_f = None

        return lat_f, lon_f, alt_f

        # for _, row in df.iterrows():
        #     lat = row[lat_col]
        #     lon = row[lon_col]
        #     alt = row[alt_col]
        #     if pd.notnull(lat) and pd.notnull(lon) and pd.notnull(alt):
        #         # Convert to float in case they are strings
        #         lat_f = float(lat)
        #         lon_f = float(lon)
        #         alt_f = float(alt)
        #         return lat_f, lon_f, alt_f
        # return None, None, None

    def _find_home_position(self, df: pd.DataFrame, lat_col: str, lon_col: str, alt_col: str) -> Tuple[float, float, float]:
        """
        Find the home position as a function of the log file type.

        Args:
            df (pd.DataFrame): DataFrame containing latitude and longitude columns.
            lat_col (str): Name of the latitude column.
            lon_col (str): Name of the longitude column.
            alt_col (str): Name of the altitude column.

        Returns:
            Tuple[float, float, float]: Home latitude, longitude, and altitude values.
        """

        home_lat = None
        home_lon = None
        home_alt = None

        if self.current_log.user_home_position is not None:
            home_lat, home_lon, home_alt = self.current_log.user_home_position

        else:
            if self.current_log.log_file_type == "csv":
                home_lat, home_lon, home_alt = self._find_initial_valid_gps_data(df, lat_col, lon_col, alt_col)

            elif self.current_log.log_file_type == "tlog":
                home_lat, home_lon, home_alt = self._find_initial_valid_gps_data(df, lat_col, lon_col, alt_col)

            elif self.current_log.log_file_type == "bin":
                # For bin files, check if "ORGN.Lat (deg)" and "ORGN.Lng (deg)" exist
                if 'ORGN.Lat (deg)' in df.columns and 'ORGN.Lng (deg)' in df.columns:
                    home_lat, home_lon, home_alt = self._find_initial_valid_gps_data(df, 'ORGN.Lat (deg)', 'ORGN.Lng (deg)', 'ORGN.Alt (m)')
                else:
                    home_lat, home_lon, home_alt = self._find_initial_valid_gps_data(df, lat_col, lon_col, alt_col)
            else:
                home_lat = None
                home_lon = None
                home_alt = None

        return home_lat, home_lon, home_alt

    def _extract_metadata(self):
        """
        Extract metadata such as sample rate, duration, and channel info from processed data.
        """

        if self.current_log is None or self.current_log.processed_data is None:
            return

        df = self.current_log.processed_data

        # Calculate basic statistics
        self.current_log.metadata = {
            'num_samples': len(df),
            'num_channels': len(df.columns),
            'channels': list(df.columns),
            'file_size': self.current_log.file_path.stat().st_size if self.current_log.file_path else 0,
            'imported_messages': self.imported_message_types,
            'non_imported_messages': self.nonimported_message_types
        }

        # Try to find time column and calculate duration/sample rate
        time_cols = [col for col in df.columns if 'elapsedtime' in col.lower()]

        if time_cols:
            time_col = time_cols[0]
            time_data = pd.to_numeric(df[time_col], errors='coerce').dropna()

            if len(time_data) > 1:
                self.current_log.duration = float(
                    time_data.iloc[-1] - time_data.iloc[0])
                time_diff = time_data.diff().dropna()
                if len(time_diff) > 0:
                    avg_interval = time_diff.mean()
                    if avg_interval > 0:
                        self.current_log.sample_rate = 1.0 / avg_interval

        # Store additional metadata
        self.current_log.metadata.update({
            'duration': self.current_log.duration,
            'sample_rate': self.current_log.sample_rate,
            'time_column': time_cols[0] if time_cols else None
        })

    def get_channel_data(self, channel_name: str) -> Optional[pd.Series]:
        """
        Get data for a specific channel.

        Args:
            channel_name (str): Name of the channel.

        Returns:
            Optional[pd.Series]: Data for the channel, or None if not found.
        """

        if (self.current_log is None or
            self.current_log.processed_data is None or
                channel_name not in self.current_log.processed_data.columns):
            return None

        return self.current_log.processed_data[channel_name]

    def get_time_data(self) -> Optional[pd.Series]:
        """
        Get time data for the current log, either from a time column or generated from sample rate.

        Returns:
            Optional[pd.Series]: Time data, or None if unavailable.
        """
        if self.current_log is None or self.current_log.processed_data is None:
            return None

        time_col = self.current_log.metadata.get('time_column')
        if time_col:
            return pd.to_numeric(self.current_log.processed_data[time_col], errors='coerce')

        # If no time column, create index-based time
        if self.current_log.sample_rate > 0:
            return pd.Series(np.arange(len(self.current_log.processed_data))
                             / self.current_log.sample_rate)

        return None

    def get_summary_stats(self, channel_name: str) -> Optional[Dict[str, float]]:
        """
        Get summary statistics (mean, std, min, max, median, count) for a channel.

        Args:
            channel_name (str): Name of the channel.

        Returns:
            Optional[Dict[str, float]]: Dictionary of summary statistics, or None if unavailable.
        """

        data = self.get_channel_data(channel_name)
        if data is None:
            return None

        numeric_data = pd.to_numeric(data, errors='coerce').dropna()
        if len(numeric_data) == 0:
            return None

        return {
            'mean': float(numeric_data.mean()),
            'std': float(numeric_data.std()),
            'min': float(numeric_data.min()),
            'max': float(numeric_data.max()),
            'median': float(numeric_data.median()),
            'count': len(numeric_data)
        }

    def generate_gps_derived_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate custom data channels based on existing data.
        1. GPS.X (m) and GPS.Y (m): X and Y excursions in meters from the center GPS point.
        2. CUSTOM.DistFromHome (m): Distance from home position in meters.
        3. CUSTOM.BearingToHome (deg): Bearing to home position in degrees.
        4. CUSTOM.ElevationToHome (deg): Elevation angle to home position in degrees.

        Args:
            df (pd.DataFrame): DataFrame containing the processed log data.

        Returns:
            pd.DataFrame: DataFrame with additional custom data channels.
        """
        if df is None or df.empty:
            return df

        lat_col = None
        lon_col = None

        lat_col = df.columns[df.columns.str.startswith('GPS.Lat')][0] if any(
            df.columns.str.startswith('GPS.Lat')) else None
        lon_col = df.columns[df.columns.str.startswith('GPS.Lon')][0] if any(
            df.columns.str.startswith('GPS.Lon')) else None

        # Some longitude fields in dataflash logs start with "Lng" rather than "Lon"
        if lon_col is None:
            lon_col = df.columns[df.columns.str.startswith('GPS.Lng')][0] if any(
                df.columns.str.startswith('GPS.Lng')) else None

        # Make this case insensitive
        alt_col = df.columns[df.columns.str.lower().str.startswith('gps.alt')][0] if any(
            df.columns.str.lower().str.startswith('gps.alt')) else None

        # Allow for different log file types
        if self.current_log.log_file_type == "csv":
            # Generate a CUSTOM.GPSValid column if the lon_col and lat_col exist and are numeric
            if lat_col is not None and lon_col is not None and 'GPS.Clock' in df.columns:
                # fix_valid is True if GPS.Clock is not an empty string or NaN
                fix_valid = df['GPS.Clock'].str.strip().ne('') & df['GPS.Clock'].notna()
                df['CUSTOM.GPSValid'] = df[lat_col].notna() & df[lon_col].notna() & fix_valid
            elif lat_col is not None and lon_col is not None:
                df['CUSTOM.GPSValid'] = df[lat_col].notna() & df[lon_col].notna()
            else:
                df['CUSTOM.GPSValid'] = False

        elif self.current_log.log_file_type == "tlog":
            # Generate a CUSTOM.GPSValid column if the lon_col and lat_col exist and are numeric, and
            # the GPS.FixType column exists and is >=3
            if lat_col is not None and lon_col is not None and 'GPS.FixType' in df.columns:
                fix_valid = pd.to_numeric(df['GPS.FixType'], errors='coerce').fillna(0) >= 3.0
                df['CUSTOM.GPSValid'] = (df[lat_col].notna() & df[lon_col].notna() & fix_valid)
            elif lat_col is not None and lon_col is not None:
                df['CUSTOM.GPSValid'] = (df[lat_col].notna() & df[lon_col].notna())
            else:
                df['CUSTOM.GPSValid'] = False

        elif self.current_log.log_file_type == "bin":
            if lat_col is not None and lon_col is not None and 'GPS.Status' in df.columns:
                fix_valid = pd.to_numeric(df['GPS.Status'], errors='coerce').fillna(0) >= 3
                df['CUSTOM.GPSValid'] = (df[lat_col].notna() & df[lon_col].notna() & fix_valid)
            elif lat_col is not None and lon_col is not None:
                df['CUSTOM.GPSValid'] = df[lat_col].notna() & df[lon_col].notna()
            else:
                df['CUSTOM.GPSValid'] = False

        if lat_col is not None and lon_col is not None:
            x, y = self._compute_xy_excursions(df, lat_col, lon_col)
            df['GPS.X (m)'] = x
            df['GPS.Y (m)'] = y

            # Use _find_first_valid_lat_lon to find the first valid GPS coordinates and save
            # them as home position
            home_lat, home_lon, home_alt = self._find_home_position(df, lat_col, lon_col, alt_col)
            if home_lat is not None and home_lon is not None:
                df['CUSTOM.DistFromHome (m)'] = self._compute_distance_from_target(
                    df, lat_col, lon_col, home_lat, home_lon)
                df['CUSTOM.BearingToHome (deg)'] = self._compute_bearing_to_target(
                    df, lat_col, lon_col, home_lat, home_lon)

                if alt_col is not None:
                    # If altitude column exists, compute elevation angle to home. Assume
                    # home altitude is 0.0 m until some better approach is found.
                    df['CUSTOM.ElevationToHome (deg)'] = self._compute_elevation_to_target(
                        df, lat_col, lon_col, alt_col, home_lat, home_lon, home_alt)

        return df


    def export_filtered_data(self, output_path: str, channels: Optional[List[str]] = None,
                             start_time: Optional[float] = None,
                             end_time: Optional[float] = None) -> bool:
        """
        Export filtered log data to a CSV file, optionally filtering by channels and time range.

        Args:
            output_path (str): Path to output CSV file.
            channels (Optional[List[str]]): List of channels to export.
            start_time (Optional[float]): Start time for filtering.
            end_time (Optional[float]): End time for filtering.

        Returns:
            bool: True if export was successful, False otherwise.
        """
        if self.current_log is None or self.current_log.processed_data is None:
            return False

        try:
            df = self.current_log.processed_data.copy()

            # Filter by time if specified
            if start_time is not None or end_time is not None:
                time_data = self.get_time_data()
                if time_data is not None:
                    mask = pd.Series(True, index=df.index)
                    if start_time is not None:
                        mask &= (time_data >= start_time)
                    if end_time is not None:
                        mask &= (time_data <= end_time)
                    df = df[mask]

            # Filter by channels if specified
            if channels:
                available_channels = [
                    ch for ch in channels if ch in df.columns]
                if available_channels:
                    df = df[available_channels]

            # Export to CSV
            df.to_csv(output_path, index=False)
            return True

        except Exception as e:
            print(f"Error exporting data: {e}")
            return False
