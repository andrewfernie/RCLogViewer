"""
Copyright Andrew Fernie, 2025

log_processor.py

Provides classes and functions for loading, parsing, processing, and exporting RC flight log data
in CSV format, metadata extraction, channel access, and summary statistics.
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
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


class LogProcessor:
    """
    Main class for loading, parsing, processing, and exporting RC flight log data in a CSV file.

    Initialize LogProcessor with no loaded log and supported formats.
    """

    def __init__(self):
        self.current_log: Optional[LogData] = None
        self.supported_formats = ['.csv', '.tlog', '.bin']

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

            # Remove empty columns
            df = df.dropna(axis=1, how='all')

            # Split GPS column if present
            if 'GPS' in df.columns:
                gps_split = df['GPS'].str.split(' ', expand=True)
                df['GPS.Latitude'] = gps_split[0]
                df['GPS.Longitude'] = gps_split[1]
                df = df.drop(columns=['GPS'])

            # Compute X/Y excursions in meters from center GPS point if GPS columns exist
            if 'GPS.Longitude' in df.columns and 'GPS.Latitude' in df.columns:
                # Convert to float in case they are strings
                df['GPS.LongitudeFloat'] = df['GPS.Longitude'].astype(float)
                df['GPS.LatitudeFloat'] = df['GPS.Latitude'].astype(float)
                lon0 = df['GPS.LongitudeFloat'].mean()
                lat0 = df['GPS.LatitudeFloat'].mean()
                # Use pyproj for accurate projection (WGS84)
                proj = Proj(proj='aeqd', lat_0=lat0, lon_0=lon0, datum='WGS84')
                x, y = proj(df['GPS.LongitudeFloat'].values,
                            df['GPS.LatitudeFloat'].values)
                df['GPS.X (m)'] = x
                df['GPS.Y (m)'] = y
                df = df.drop(
                    columns=['GPS.LatitudeFloat', 'GPS.LongitudeFloat'])
                import_status += "Contains GPS data.\n"
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

            # Compute LiPo Total (V) if any "LiPo<N> (V)"" columns exist
            lipo_cols = [col for col in df.columns if re.match(
                r"POWER.LiPo\d+ \(V\)", col)]

            if lipo_cols:
                df['POWER.LiPo.Total (V)'] = df[lipo_cols].sum(axis=1)
                import_status += "Generated 'LiPo.Total (V)' data.\n"

            # Compute Power(W) if VFAS(V) and Current(A) are present
            if 'POWER.VFAS (V)' in df.columns and 'POWER.Current (A)' in df.columns:
                df['POWER.Power (W)'] = df['POWER.VFAS (V)'] * \
                    df['POWER.Current (A)']
                import_status += "Generated 'Power (W)' data.\n"

            # Sort columns alphabetically
            df = df[sorted(df.columns)]

            # Store processed data
            self.current_log.processed_data = df
            self.current_log.channels = list(df.columns)

            return True

        except Exception as e:
            print(f"Error parsing CSV file: {e}")
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

            # TLOG files are essentially records of MAVLINK messages.
            # See https://mavlink.io/en/messages/common.html for message definitions.
            #
            # They can include time series data as well as one-time parameters, file transfers, etc.
            # We are concerned primarily with time series data, and even for time series data, the
            # content of the TLOG file will depend on the specific MAVLink messages being sent and
            # received. So, we need to define the message types we are interested in, and this is
            # done in the config file through an object "mavlink_messages".
            desired_msg_types = list(config.get("mavlink_messages", {}).keys())

            # Retrieve the scaling dictionary for unit conversions from the config file. The names
            # are those found in the pymavlink message fieldunits_by_name attribute.
            scaling_dict = config.get("scaling", {})

            # Iterate through all messages in the log file
            while True:
                msg = mlog.recv_match(type=desired_msg_types, blocking=False)
                if msg is None:
                    break

                percent_complete = mlog.percent
                if progress_callback:
                    progress_callback(percent_complete)

                msg_datetime = pd.to_datetime(datetime.fromtimestamp(msg._timestamp
                                                                     ).strftime('%Y-%m-%d %H:%M:%S.%f'))

                msg_dict = msg.to_dict()

                # Get the "group" to which each parameter is assigned, and to be used as the prefix to the DataFrame column.
                msg_group = config.get("mavlink_messages", {}).get(
                    msg.get_type(), {}).get("group", "UNKNOWN")

                # Get the timestamp for this message and make it the first entry in the data_list
                data_list = {'DateTime': msg_datetime}

                # Check the field "all_channels", which indicates that all channels found in the message
                # should be imported.
                all_channels = config.get("mavlink_messages", {}).get(
                    msg.get_type(), {}).get("all_channels", 0)

                fieldnames = msg.get_fieldnames()
                num_fields = len(fieldnames)

                # Find the fields listed in the config file we said we are interested in
                config_msg_fields = config.get("mavlink_messages", {}).get(
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

            if not data:
                return False

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

            # Compute X/Y excursions in meters from center GPS point if GPS columns exist\
            # If there is a column in df that starts with 'GPS.Longitude'

            # Find a column in df that starts with 'GPS.Latitude'
            lat_col = df.columns[df.columns.str.startswith('GPS.Latitude')]
            lon_col = df.columns[df.columns.str.startswith('GPS.Longitude')]

            if lon_col is not None and lat_col is not None:
                # Convert to float in case they are strings
                df['GPS.LongitudeFloat'] = df[lon_col].astype(float)
                df['GPS.LatitudeFloat'] = df[lat_col].astype(float)
                lon0 = df['GPS.LongitudeFloat'].mean()
                lat0 = df['GPS.LatitudeFloat'].mean()
                # Use pyproj for accurate projection (WGS84)
                proj = Proj(proj='aeqd', lat_0=lat0, lon_0=lon0, datum='WGS84')
                x, y = proj(df['GPS.LongitudeFloat'].values,
                            df['GPS.LatitudeFloat'].values)
                df['GPS.X (m)'] = x
                df['GPS.Y (m)'] = y
                df = df.drop(
                    columns=['GPS.LatitudeFloat', 'GPS.LongitudeFloat'])
                import_status += "Contains GPS data.\n"
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
            return True

        except Exception as e:
            print(f"Error parsing tlog file: {e}")
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

            # Dataflash log (.bin) files can include time series data as well as one-time
            # parameters, etc.

            # Message definitions can be found here:
            # https://ardupilot.org/copter/docs/logmessages.html#logmessages
            # https://ardupilot.org/plane/docs/logmessages.html#logmessages

            # We are concerned primarily with time series data, and even
            # for time series data, the content of the bin will depend on how the flight
            # controller has been configured. So, we need to define the message types we
            # are interested in, and this is done in the config file through an object
            # "dataflash_messages".

            desired_msg_types = list(config.get(
                "dataflash_messages", {}).keys())

            # Retrieve the scaling dictionary for unit conversions from the config file. The names
            # are those found in the pymavlink message fieldunits_by_name attribute.
            scaling_dict = config.get("scaling", {})

            # Iterate through all messages in the log file
            while True:
                msg = mlog.recv_match(type=desired_msg_types, blocking=False)
                if msg is None:
                    break

                percent_complete = mlog.percent
                if progress_callback:
                    progress_callback(percent_complete)

                # Get the timestamp for this message
                msg_datetime = pd.to_datetime(datetime.fromtimestamp(msg._timestamp
                                                                     ).strftime('%Y-%m-%d %H:%M:%S.%f'))

                msg_dict = msg.to_dict()

                # Get the "group" to which each parameter is assigned, and to be used as the prefix to the DataFrame column.
                msg_group = config.get("dataflash_messages", {}).get(
                    msg.get_type(), {}).get("group", "UNKNOWN")

                # Get the timestamp for this message and make it the first entry in the data_list
                data_list = {'DateTime': msg_datetime}

                # Check the field "all_channels", which indicates that all channels found in the message
                # should be imported.
                all_channels = config.get("dataflash_messages", {}).get(
                    msg.get_type(), {}).get("all_channels", 0)

                fieldnames = msg.get_fieldnames()
                num_fields = len(fieldnames)

                # Find the fields listed in the config file we said we are interested in
                config_msg_fields = config.get("dataflash_messages", {}).get(
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

            if not data:
                return False

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

            # Find a column in df that starts with 'GPS.Lat' or 'GPS.Lon'
            lat_col = df.columns[df.columns.str.startswith('GPS.Lat')]
            lon_col = df.columns[df.columns.str.startswith('GPS.Lon')]

            # Some longitude fields in dataflash logs start with "Lng" rather than "Lon"
            if lon_col.empty:
                lon_col = df.columns[df.columns.str.startswith('GPS.Lng')]

            if not lon_col.empty and not lat_col.empty:
                # Compute X/Y excursions in meters from center GPS point if GPS columns exist
                # Convert to float in case they are strings
                df['GPS.LongitudeFloat'] = df[lon_col].astype(float)
                df['GPS.LatitudeFloat'] = df[lat_col].astype(float)
                lon0 = df['GPS.LongitudeFloat'].mean()
                lat0 = df['GPS.LatitudeFloat'].mean()

                # Use pyproj for accurate projection (WGS84)
                proj = Proj(proj='aeqd', lat_0=lat0, lon_0=lon0, datum='WGS84')
                x, y = proj(df['GPS.LongitudeFloat'].values,
                            df['GPS.LatitudeFloat'].values)
                df['GPS.X (m)'] = x
                df['GPS.Y (m)'] = y
                df = df.drop(
                    columns=['GPS.LatitudeFloat', 'GPS.LongitudeFloat'])
                import_status += "Contains GPS data.\n"
            else:
                import_status += "No GPS data found.\n"

            # Sort columns alphabetically
            df = df[sorted(df.columns)]

            # Store processed data
            self.current_log.processed_data = df
            self.current_log.channels = list(df.columns)
            return True

        except Exception as e:
            print(f"Error parsing bin file: {e}")
            return False

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
            'file_size': self.current_log.file_path.stat().st_size if self.current_log.file_path else 0
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
